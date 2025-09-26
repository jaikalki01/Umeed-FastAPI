import time
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, or_, desc
from sqlalchemy.orm import Session, aliased
from typing import List, Dict

from fastapi import WebSocket, WebSocketDisconnect, Depends, APIRouter, HTTPException, Request, Query
from starlette import status
from starlette.responses import JSONResponse

from app.models.models import ChatMessage, User, ChatRoom, AgoraConfig, Notification, india_tz, BlockedProfile
from app.schemas.chat import MessageResponse, UserResponse
from app.utils.authenticate import get_current_user, get_current_user_ws
from app.utils.database import get_db
from app.crud.RtcTokenBuilder import RtcTokenBuilder, Role_Attendee
router = APIRouter()





@router.get("/users_with_last_message")
def get_chat_users_with_last_message(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Alias for joining both sender and receiver roles
    user_alias = aliased(User)

    # Subquery to get last message per user (sender/receiver pair)
    subq = (
        db.query(
            func.max(ChatMessage.id).label("last_msg_id")
        )
        .filter(
            or_(
                ChatMessage.sender_id == current_user.id,
                ChatMessage.receiver_id == current_user.id
            )
        )
        .group_by(
            func.least(ChatMessage.sender_id, ChatMessage.receiver_id),
            func.greatest(ChatMessage.sender_id, ChatMessage.receiver_id)
        )
        .subquery()
    )

    # Now get full message info from last message IDs
    messages = (
        db.query(ChatMessage)
        .join(subq, ChatMessage.id == subq.c.last_msg_id)
        .order_by(desc(ChatMessage.timestamp))
        .all()
    )

    result = []
    blocked_cache = {}
    for msg in messages:
        other_user = msg.receiver if msg.sender_id == current_user.id else msg.sender
        other_id = other_user.id
        if other_id not in blocked_cache:
            blocked_by_current = db.query(BlockedProfile).filter(
                BlockedProfile.blocker_id == current_user.id,
                BlockedProfile.blocked_user_id == other_id
            ).first() is not None

            blocked_by_other = db.query(BlockedProfile).filter(
                BlockedProfile.blocker_id == other_id,
                BlockedProfile.blocked_user_id == current_user.id
            ).first() is not None

            blocked_cache[other_id] = (blocked_by_current, blocked_by_other)

        blocked_by_current, blocked_by_other = blocked_cache[other_id]
        result.append({
            "user": other_user,
            "isBlocked": blocked_by_current,  # current_user blocked the other user
            "isBlockedByOther": blocked_by_other,  # other user blocked current_user
            "last_message": msg.message,
            "timestamp": msg.timestamp,
            "is_read":msg.is_read
        })

    return result

# @router.get("/chat/history/{other_user_id}", response_model=List[MessageResponse])
# def get_chat_history(
#     other_user_id: str,
#     db: Session = Depends(get_db),
#     current_user = Depends(get_current_user)
# ):
#     # Get full chat history
#     messages = db.query(ChatMessage).filter(
#         ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == other_user_id)) |
#         ((ChatMessage.sender_id == other_user_id) & (ChatMessage.receiver_id == current_user.id))
#     ).order_by(ChatMessage.timestamp.asc()).all()
#
#     # Mark messages sent to current user by other_user as read
#     unread_messages = db.query(ChatMessage).filter(
#         ChatMessage.sender_id == other_user_id,
#         ChatMessage.receiver_id == current_user.id,
#         ChatMessage.is_read == False
#     ).all()
#
#     for msg in unread_messages:
#         msg.is_read = True
#
#     db.commit()
#
#     return messages




@router.get("/chat/history/{other_user_id}", response_model=List[MessageResponse])
async def get_chat_history(
    other_user_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),  # default 20, max 100
    offset: int = Query(0, ge=0)            # start from 0
):
    # Get paginated chat history
    messages = db.query(ChatMessage).filter(
        ((ChatMessage.sender_id == current_user.id) & (ChatMessage.receiver_id == other_user_id)) |
        ((ChatMessage.sender_id == other_user_id) & (ChatMessage.receiver_id == current_user.id))
    ).order_by(ChatMessage.timestamp.desc()) \
     .offset(offset) \
     .limit(limit) \
     .all()

    # Mark unread messages as read (only for messages sent TO current user by other_user)
    # unread_messages = db.query(ChatMessage).filter(
    #     ChatMessage.sender_id == other_user_id,
    #     ChatMessage.receiver_id == current_user.id,
    #     ChatMessage.is_read == False
    # ).all()
    #
    # for msg in unread_messages:
    #     msg.is_read = True
    db.query(ChatMessage).filter(
        ChatMessage.sender_id == other_user_id,
        ChatMessage.receiver_id == current_user.id,
        ChatMessage.is_read == False
    ).update({ChatMessage.is_read: True}, synchronize_session=False)

    #db.commit()

    db.commit()
    await push_unread_counts(db, current_user.id)
    return messages




active_connections: Dict[str, WebSocket] = {}
user_rooms = defaultdict(dict)  # user_id -> room_id

@router.websocket("/ws/chat/{other_user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    other_user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    sender_id = current_user.id
    receiver_id = other_user_id

    # 1. Update user online status = True
    current_user.onlineUsers = True
    db.commit()

    try:
        # Ensure receiver_id format
        receiver_id = receiver_id  # Keep as string if you're not using int

        # 2. Get or create chat room
        room = db.query(ChatRoom).filter(
            ((ChatRoom.user1_id == sender_id) & (ChatRoom.user2_id == receiver_id)) |
            ((ChatRoom.user1_id == receiver_id) & (ChatRoom.user2_id == sender_id))
        ).first()

        if not room:
            room = ChatRoom(user1_id=sender_id, user2_id=receiver_id)
            db.add(room)
            db.commit()
            db.refresh(room)

        room_id = room.id

        active_connections[sender_id] = websocket
        user_rooms[sender_id][receiver_id] = room_id

        while True:
            data = await websocket.receive_text()

            # 3. Save message with is_read=False
            chat_msg = ChatMessage(
                room_id=room_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                message=data,
                is_read=False
            )
            db.add(chat_msg)
            db.commit()
            db.refresh(chat_msg)
            await push_unread_counts(db, chat_msg.receiver_id)
            message_data = {
                "from_id": sender_id,
                "to_id": receiver_id,
                "message": data,
                "timestamp": chat_msg.timestamp.isoformat(),
                "id": chat_msg.id,
                "is_read": chat_msg.is_read
            }

            # 4. Send to receiver if online
            if receiver_id in active_connections:
                await active_connections[receiver_id].send_json(message_data)

            # 5. Echo back to sender (UI confirmation)
            await websocket.send_json(message_data)

    except WebSocketDisconnect:
        # 6. On disconnect → mark user offline
        current_user.onlineUsers = False
        db.commit()

        if sender_id in active_connections:
            del active_connections[sender_id]


@router.get('/agora/token/videogenerate')
async def generate_agora_token_self(other_user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)):


    uid_user = other_user_id
    if not uid_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UID User not found")
    if current_user.status != "Paid":
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Or use another code like 202
            content={"warning": "You are not a Umeed Prime Member"}
        )

    if current_user.video_min < 1:
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Or use another code like 202
            content={"warning": "Your video call minutes are over. Please subscribe to get more video call minutes."}
        )

    videoMins = (current_user.video_min or 0) * 60

    if videoMins <= 0:
        raise HTTPException(status_code=400, detail="No video minutes available.")

    user_status = {}
    room = db.query(ChatRoom).filter(
        ((ChatRoom.user1_id == current_user.id) & (ChatRoom.user2_id == uid_user)) |
        ((ChatRoom.user1_id == uid_user) & (ChatRoom.user2_id == current_user.id))
    ).first()

    if not room:
        room = ChatRoom(user1_id=current_user.id, user2_id=uid_user)
        db.add(room)
        db.commit()
        db.refresh(room)

    room= room.id

    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    get_app_id = db.query(AgoraConfig).filter(AgoraConfig.status == True).first()

    if not get_app_id:
        raise HTTPException(status_code=404, detail="Active Agora configuration not found.")

    # Validate fields
    if not get_app_id.app_id or not get_app_id.app_certificate or not get_app_id.app_name:
        raise HTTPException(status_code=400, detail="Agora configuration is incomplete.")

    appId = get_app_id.app_id
    appCertificate = get_app_id.app_certificate
    app_name = get_app_id.app_name

    appID = appId #"fc22b1634fcf4b5eacef4b96cc41cc17"
    appCertificate =appCertificate #"fc484dd33b904722ae0e52fc9c17333e"
    channelName = f"{current_user.id}-{other_user_id}"
    userAccount = 0
    expireTimeInSeconds = videoMins
    currentTimestamp = int(time.time())
    privilegeExpiredTs = currentTimestamp + expireTimeInSeconds

    token = RtcTokenBuilder.buildTokenWithAccount(
        appID, appCertificate, channelName, userAccount, Role_Attendee, privilegeExpiredTs)

    return JSONResponse({'video_token': token, "channelName": channelName, 'user': current_user.id,
                         'timer': videoMins, 'userType': current_user.status, "appID":app_name})


@router.get('/agora/token/Voicegenerate')
async def generate_agora_token_Voiceself(other_user_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)):

    uid_user = other_user_id
    if not uid_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UID User not found")
    if current_user.status != "Paid":
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Or use another code like 202
            content={"warning": "You are not a Umeed Prime Member"}
        )

    if current_user.voice_min < 1:
        return JSONResponse(
            status_code=status.HTTP_200_OK,  # Or use another code like 202
            content={"warning": "Your video call minutes are over. Please subscribe to get more video call minutes."}
        )

    room = db.query(ChatRoom).filter(
        ((ChatRoom.user1_id == current_user.id) & (ChatRoom.user2_id == uid_user)) |
        ((ChatRoom.user1_id == uid_user) & (ChatRoom.user2_id == current_user.id))
    ).first()

    if not room:
        room = ChatRoom(user1_id=current_user.id, user2_id=uid_user)
        db.add(room)
        db.commit()
        db.refresh(room)

    room = room.id
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    videoMins = (current_user.voice_min or 0) * 60

    if videoMins <= 0:
        raise HTTPException(status_code=400, detail="No video minutes available.")

    get_app_id = db.query(AgoraConfig).filter(AgoraConfig.status == True).first()

    if not get_app_id:
        raise HTTPException(status_code=404, detail="Active Agora configuration not found.")

    # Validate fields
    if not get_app_id.app_id or not get_app_id.app_certificate or not get_app_id.app_name:
        raise HTTPException(status_code=400, detail="Agora configuration is incomplete.")

    appId = get_app_id.app_id
    appCertificate = get_app_id.app_certificate
    app_name = get_app_id.app_name

    appID = appId#"3a39af44074a40bebc2fff2cba7437e5"
    appCertificate = appCertificate #"95e4a3c81798428a8d5a36d51862e375"
    channelName = f"{current_user.id}-{other_user_id}"
    userAccount = str(current_user.id)
    expireTimeInSeconds = videoMins
    currentTimestamp = int(time.time())
    privilegeExpiredTs = currentTimestamp + expireTimeInSeconds

    token = RtcTokenBuilder.buildTokenWithAccount(
        appID, appCertificate, channelName, userAccount, Role_Attendee, privilegeExpiredTs)

    return JSONResponse({'audio_token': token, "channelName": channelName, 'user': current_user.id,
                         'timer': videoMins, 'userType': current_user.status, "appID":app_name})


@router.post('/uservideocallstatus')
async def uservideocallstatus(userId:str, durationSeconds:str, db: Session = Depends(get_db)):
    try:
        #data = await request.json()
        user = userId
        duration = durationSeconds
        videoMins = int(duration) / 60
        get_user = db.query(User).filter(User.id==user).first()
        if get_user:
            get_user.video_min -= videoMins
            db.commit()
        return JSONResponse({'message': 'Data received successfully'})
    except Exception as e:
        return JSONResponse({'error': f'Error processing request: {str(e)}'}, status_code=500)


@router.post('/useraudiocallstatus')
async def useraudiocallstatus(userId:str, durationSeconds:str, db: Session = Depends(get_db)):
    try:
        #data = await request.json()
        user = userId
        duration = durationSeconds
        voiceMins = int(duration) / 60
        get_user = db.query(User).filter(User.id==user).first()
        if get_user:
            get_user.voice_min -= voiceMins
            db.commit()
            db.refresh(get_user)
        return JSONResponse({'message': 'Data received successfully'})
    except Exception as e:
        return JSONResponse({'error': f'Error processing request: {str(e)}'}, status_code=500)


active_notification_connections = {}

@router.websocket("/ws/unread")
async def websocket_unread(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    user_id = current_user.id
    active_notification_connections[user_id] = websocket

    try:
        while True:
            # Keep connection alive (no need for client messages)
            await websocket.receive_text()
    except WebSocketDisconnect:
        if user_id in active_notification_connections:
            del active_notification_connections[user_id]

@router.websocket("/ws/unread")
async def websocket_unread(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_ws)
):
    await websocket.accept()
    user_id = current_user.id

    # register connection
    active_notification_connections[user_id].add(websocket)

    # mark user online in DB (only commit if change needed)
    try:
        # refresh / re-query user to ensure session has latest object
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.onlineUsers:
            user.onlineUsers = True
            db.commit()
    except Exception:
        # log if needed, but continue — we don't want DB errors to block the socket
        db.rollback()

    try:
        while True:
            # keep the connection alive; client may not send messages, but this will
            # receive when they do. You can also await websocket.receive_text() or implement ping/pong.
            await websocket.receive_text()
    except WebSocketDisconnect:
        # normal disconnect
        pass
    except Exception:
        # handle unexpected errors (optionally log)
        pass
    finally:
        # cleanup this websocket from the user's set
        user_conns = active_notification_connections.get(user_id)
        if user_conns and websocket in user_conns:
            user_conns.remove(websocket)
            if not user_conns:
                # no more active sockets for this user -> mark offline
                try:
                    # set offline and update lastSeen
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        user.onlineUsers = False
                        user.lastSeen = datetime.now(india_tz)
                        db.commit()
                except Exception:
                    db.rollback()
                # remove empty entry from dict
                del active_notification_connections[user_id]

async def push_unread_counts(db: Session, user_id: str):
    """Send updated unread counts to user if connected via WebSocket"""
    if user_id not in active_notification_connections:
        return

    notif_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.receiver_id == user_id, Notification.is_read == False)
        .scalar()
    )
    chat_count = (
        db.query(func.count(ChatMessage.id))
        .filter(ChatMessage.receiver_id == user_id, ChatMessage.is_read == False)
        .scalar()
    )

    payload = {
        #"notify_unread": notif_count,
        "chat_unread": chat_count,
        #"total_unread": (notif_count or 0) + (chat_count or 0),
    }

    try:
        await active_notification_connections[user_id].send_json(payload)
    except Exception:
        # If sending fails → drop connection
        del active_notification_connections[user_id]
