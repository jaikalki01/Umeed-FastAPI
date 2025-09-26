import re
import threading
from datetime import datetime, timedelta

import firebase_admin
import razorpay
from fastapi import HTTPException
from sqlalchemy import func, text, desc, cast, Integer, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import User, ProfileView, MatchRequest, BlockedProfile, SavedProfile, Notification, \
    NotificationStatus, india_tz, ChatLog
from app.schemas.user_schemas import UserPublicResponse
from firebase_admin import credentials, messaging
from sqlalchemy import or_

user_id_lock = threading.Lock()
client = razorpay.Client(auth=("rzp_live_Z0qfc9VQ6G85BW", "xUNObYwF43SOr1sDioxV7xio"))
cred = credentials.Certificate('umeed-2d7e6-firebase-adminsdk-s32ij-1c9976d6c1.json')
firebase_admin.initialize_app(cred)




def generate_sequential_user_id(db):
    prefix = "UD"
    # Skip the first two characters ("UD") and cast the rest to integer for proper sorting
    last_user = (
        db.query(User)
        .filter(User.id.like(f"{prefix}%"))
        .order_by(desc(cast(func.substr(User.id, len(prefix)+1), Integer)))
        .first()
    )

    if last_user:
        last_number = int(last_user.id[len(prefix):])
    else:
        last_number = 0

    next_number = last_number + 1
    return f"{prefix}{str(next_number).zfill(4)}"  # UD00000001


def paginate(query, page: int, limit: int):
    total = query.count()
    skip = (page - 1) * limit
    items = query.offset(skip).limit(limit).all()
    has_next = skip + limit < total
    return total, has_next, items


def mark_view_as_read(view_id: str, db: Session):
    view = db.query(ProfileView).filter(ProfileView.id == view_id).first()
    if view:
        view.is_read = True
        db.commit()
        return True
    return False


def get_user_public_response(
    user: User,
    current_user_id: str,
    db: Session
) -> UserPublicResponse:
    # Find latest match request in either direction
    match = db.query(MatchRequest).filter(
        ((MatchRequest.sender_id == current_user_id) & (MatchRequest.receiver_id == user.id)) |
        ((MatchRequest.sender_id == user.id) & (MatchRequest.receiver_id == current_user_id))
    ).order_by(MatchRequest.created_at.desc()).first()

    # Status logic
    if match:
        match_status = match.status  # 'pending' or 'accepted'
    else:
        match_status = "none"

    # Is blocked
    is_blocked = db.query(BlockedProfile).filter_by(
        blocker_id=current_user_id,
        blocked_user_id=user.id
    ).first() is not None

    # Is saved
    is_saved = db.query(SavedProfile).filter_by(
        user_id=current_user_id,
        saved_user_id=user.id
    ).first() is not None

    return UserPublicResponse(
        **user.__dict__,
        match_status=match_status,
        isBlocked=is_blocked,
        isSaved=is_saved
    )

def build_user_response(
    target_user_id: str,
    current_user_id: str,
    db: Session
) -> UserPublicResponse:
    # Load actual user object
    user = db.query(User).filter(User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # First, check if current user sent a match request
    match = db.query(MatchRequest).filter(
        MatchRequest.sender_id == current_user_id,
        MatchRequest.receiver_id == target_user_id
    ).first()

    if match:
        is_matched = True
        match_status = "sent" if match.status == "pending" else match.status
    else:
        # Check if target user sent a match request to current user
        match = db.query(MatchRequest).filter(
            MatchRequest.sender_id == target_user_id,
            MatchRequest.receiver_id == current_user_id
        ).first()
        if match:
            is_matched = True
            match_status = "pending" if match.status == "pending" else match.status
        else:
            is_matched = False
            match_status = "none"

    #Check block status
    isBlockedByOther = db.query(BlockedProfile).filter(
        BlockedProfile.blocker_id == current_user_id,
        BlockedProfile.blocked_user_id == target_user_id
    ).first() is not None

    is_blocked = db.query(BlockedProfile).filter(
        or_(
            and_(
                BlockedProfile.blocker_id == current_user_id,
                BlockedProfile.blocked_user_id == target_user_id
            ),
            and_(
                BlockedProfile.blocker_id == target_user_id,
                BlockedProfile.blocked_user_id == current_user_id
            )
        )
    ).first() is not None


    # Check saved status
    is_saved = db.query(SavedProfile).filter(
        SavedProfile.user_id == current_user_id,
        SavedProfile.saved_user_id == target_user_id
    ).first() is not None

    return UserPublicResponse(
        **user.__dict__,
        isMatched=is_matched,
        match_status=match_status,
        isBlocked=is_blocked,
        isBlockedBySelf=isBlockedByOther,
        isSaved=is_saved
    )

def create_or_update_view_notification(
    sender_id: str,
    receiver_id: str,
    db: Session
) -> None:
    try:
        existing_notification = db.query(Notification).filter(
            Notification.sender_id == sender_id,
            Notification.receiver_id == receiver_id,
            Notification.status == NotificationStatus.view
        ).first()

        if existing_notification:
            # Update timestamp and unread status
            existing_notification.created_at = datetime.now(india_tz)
            existing_notification.is_read = False
        else:
            # Create new view notification
            new_notification = Notification(
                sender_id=sender_id,
                receiver_id=receiver_id,
                status=NotificationStatus.view,
                created_at=datetime.now(india_tz),
                is_read=False,
                message="Profile viewed"
            )
            db.add(new_notification)

        db.commit()

    except SQLAlchemyError as e:
        db.rollback()



def send_notification_to_all_user(title, body, image, token):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
                image=image
            ),
            token=token,
        )
        response = messaging.send(message)
        return True  # ✅ Notification sent successfully
    except Exception as e:
        #logging.error(f"Error sending notification: {e}")
        return False  # ❌ Failed to send



height_mapping1 = {
    1: '4ft (121 cm)',
    2: '4ft 1in (124 cm)',
    3: '4ft 2in (127 cm)',
    4: '4ft 3in (129 cm)',
    5: '4ft 4in (132 cm)',
    6: '4ft 5in (134 cm)',
    7: '4ft 6in (137 cm)',
    8: '4ft 7in (139 cm)',
    9: '4ft 8in (142 cm)',
    10: '4ft 9in (144 cm)',
    11: '4ft 10in (147 cm)',
    12: '4ft 11in (149 cm)',
    13: '5ft (152 cm)',
    14: '5ft 1in (154 cm)',
    15: '5ft 2in (157 cm)',
    16: '5ft 3in (160 cm)',
    17: '5ft 4in (162 cm)',
    18: '5ft 5in (165 cm)',
    19: '5ft 6in (167 cm)',
    20: '5ft 7in (170 cm)',
    21: '5ft 8in (172 cm)',
    22: '5ft 9in (175 cm)',
    23: '5ft 10in (177 cm)',
    24: '5ft 11in (180 cm)',
    25: '6ft (182 cm)',
    26: '6ft 1in (185 cm)',
    27: '6ft 2in (187 cm)',
    28: '6ft 3in (190 cm)',
    29: '6ft 4in (193 cm)',
    30: '6ft 5in (195 cm)',
    31: '6ft 6in (198 cm)',
    32: '6ft 7in (200 cm)',
    33: '6ft 8in (203 cm)',
    34: '6ft 9in (205 cm)',
    35: '6ft 10in (208 cm)',
    36: '6ft 11in (210 cm)',
    37: '7ft 00in (212 cm)',
}

WORLD_MOBILE_CODES = [
    {"country": "Afghanistan", "code": "93"},
    {"country": "Albania", "code": "355"},
    {"country": "Algeria", "code": "213"},
    {"country": "Andorra", "code": "376"},
    {"country": "Angola", "code": "244"},
    {"country": "Antigua and Barbuda", "code": "1268"},
    {"country": "Argentina", "code": "54"},
    {"country": "Armenia", "code": "374"},
    {"country": "Australia", "code": "61"},
    {"country": "Austria", "code": "43"},
    {"country": "Azerbaijan", "code": "994"},
    {"country": "Bahamas", "code": "1242"},
    {"country": "Bahrain", "code": "973"},
    {"country": "Bangladesh", "code": "880"},
    {"country": "Barbados", "code": "1246"},
    {"country": "Belarus", "code": "375"},
    {"country": "Belgium", "code": "32"},
    {"country": "Belize", "code": "501"},
    {"country": "Benin", "code": "229"},
    {"country": "Bhutan", "code": "975"},
    {"country": "Bolivia", "code": "591"},
    {"country": "Bosnia and Herzegovina", "code": "387"},
    {"country": "Botswana", "code": "267"},
    {"country": "Brazil", "code": "55"},
    {"country": "Brunei", "code": "673"},
    {"country": "Bulgaria", "code": "359"},
    {"country": "Burkina Faso", "code": "226"},
    {"country": "Burundi", "code": "257"},
    {"country": "Cambodia", "code": "855"},
    {"country": "Cameroon", "code": "237"},
    {"country": "Canada", "code": "1"},
    {"country": "Cape Verde", "code": "238"},
    {"country": "Central African Republic", "code": "236"},
    {"country": "Chad", "code": "235"},
    {"country": "Chile", "code": "56"},
    {"country": "China", "code": "86"},
    {"country": "Colombia", "code": "57"},
    {"country": "Comoros", "code": "269"},
    {"country": "Congo", "code": "242"},
    {"country": "Costa Rica", "code": "506"},
    {"country": "Croatia", "code": "385"},
    {"country": "Cuba", "code": "53"},
    {"country": "Cyprus", "code": "357"},
    {"country": "Czech Republic", "code": "420"},
    {"country": "Denmark", "code": "45"},
    {"country": "Djibouti", "code": "253"},
    {"country": "Dominica", "code": "1767"},
    {"country": "Dominican Republic", "code": "1809"},
    {"country": "Ecuador", "code": "593"},
    {"country": "Egypt", "code": "20"},
    {"country": "El Salvador", "code": "503"},
    {"country": "Equatorial Guinea", "code": "240"},
    {"country": "Eritrea", "code": "291"},
    {"country": "Estonia", "code": "372"},
    {"country": "Eswatini", "code": "268"},
    {"country": "Ethiopia", "code": "251"},
    {"country": "Fiji", "code": "679"},
    {"country": "Finland", "code": "358"},
    {"country": "France", "code": "33"},
    {"country": "Gabon", "code": "241"},
    {"country": "Gambia", "code": "220"},
    {"country": "Georgia", "code": "995"},
    {"country": "Germany", "code": "49"},
    {"country": "Ghana", "code": "233"},
    {"country": "Greece", "code": "30"},
    {"country": "Grenada", "code": "1473"},
    {"country": "Guatemala", "code": "502"},
    {"country": "Guinea", "code": "224"},
    {"country": "Guyana", "code": "592"},
    {"country": "Haiti", "code": "509"},
    {"country": "Honduras", "code": "504"},
    {"country": "Hungary", "code": "36"},
    {"country": "Iceland", "code": "354"},
    {"country": "India", "code": "91"},
    {"country": "Indonesia", "code": "62"},
    {"country": "Iran", "code": "98"},
    {"country": "Iraq", "code": "964"},
    {"country": "Ireland", "code": "353"},
    {"country": "Israel", "code": "972"},
    {"country": "Italy", "code": "39"},
    {"country": "Jamaica", "code": "1876"},
    {"country": "Japan", "code": "81"},
    {"country": "Jordan", "code": "962"},
    {"country": "Kazakhstan", "code": "7"},
    {"country": "Kenya", "code": "254"},
    {"country": "Kiribati", "code": "686"},
    {"country": "Korea, North", "code": "850"},
    {"country": "Korea, South", "code": "82"},
    {"country": "Kuwait", "code": "965"},
    {"country": "Kyrgyzstan", "code": "996"},
    {"country": "Laos", "code": "856"},
    {"country": "Latvia", "code": "371"},
    {"country": "Lebanon", "code": "961"},
    {"country": "Lesotho", "code": "266"},
    {"country": "Liberia", "code": "231"},
    {"country": "Libya", "code": "218"},
    {"country": "Liechtenstein", "code": "423"},
    {"country": "Lithuania", "code": "370"},
    {"country": "Luxembourg", "code": "352"},
    {"country": "Madagascar", "code": "261"},
    {"country": "Malawi", "code": "265"},
    {"country": "Malaysia", "code": "60"},
    {"country": "Maldives", "code": "960"},
    {"country": "Mali", "code": "223"},
    {"country": "Malta", "code": "356"},
    {"country": "Marshall Islands", "code": "692"},
    {"country": "Mauritania", "code": "222"},
    {"country": "Mauritius", "code": "230"},
    {"country": "Mexico", "code": "52"},
    {"country": "Micronesia", "code": "691"},
    {"country": "Moldova", "code": "373"},
    {"country": "Monaco", "code": "377"},
    {"country": "Mongolia", "code": "976"},
    {"country": "Montenegro", "code": "382"},
    {"country": "Morocco", "code": "212"},
    {"country": "Mozambique", "code": "258"},
    {"country": "Myanmar", "code": "95"},
    {"country": "Namibia", "code": "264"},
    {"country": "Nauru", "code": "674"},
    {"country": "Nepal", "code": "977"},
    {"country": "Netherlands", "code": "31"},
    {"country": "New Zealand", "code": "64"},
    {"country": "Nicaragua", "code": "505"},
    {"country": "Niger", "code": "227"},
    {"country": "Nigeria", "code": "234"},
    {"country": "North Macedonia", "code": "389"},
    {"country": "Norway", "code": "47"},
    {"country": "Oman", "code": "968"},
    {"country": "Pakistan", "code": "92"},
    {"country": "Palau", "code": "680"},
    {"country": "Palestine", "code": "970"},
    {"country": "Panama", "code": "507"},
    {"country": "Papua New Guinea", "code": "675"},
    {"country": "Paraguay", "code": "595"},
    {"country": "Peru", "code": "51"},
    {"country": "Philippines", "code": "63"},
    {"country": "Poland", "code": "48"},
    {"country": "Portugal", "code": "351"},
    {"country": "Qatar", "code": "974"},
    {"country": "Romania", "code": "40"},
    {"country": "Russia", "code": "7"},
    {"country": "Rwanda", "code": "250"},
    {"country": "Saint Kitts and Nevis", "code": "1869"},
    {"country": "Saint Lucia", "code": "1758"},
    {"country": "Saint Vincent and the Grenadines", "code": "1784"},
    {"country": "Samoa", "code": "685"},
    {"country": "San Marino", "code": "378"},
    {"country": "Saudi Arabia", "code": "966"},
    {"country": "Senegal", "code": "221"},
    {"country": "Serbia", "code": "381"},
    {"country": "Seychelles", "code": "248"},
    {"country": "Sierra Leone", "code": "232"},
    {"country": "Singapore", "code": "65"},
    {"country": "Slovakia", "code": "421"},
    {"country": "Slovenia", "code": "386"},
    {"country": "Solomon Islands", "code": "677"},
    {"country": "Somalia", "code": "252"},
    {"country": "South Africa", "code": "27"},
    {"country": "Spain", "code": "34"},
    {"country": "Sri Lanka", "code": "94"},
    {"country": "Sudan", "code": "249"},
    {"country": "Suriname", "code": "597"},
    {"country": "Sweden", "code": "46"},
    {"country": "Switzerland", "code": "41"},
    {"country": "Syria", "code": "963"},
    {"country": "Taiwan", "code": "886"},
    {"country": "Tajikistan", "code": "992"},
    {"country": "Tanzania", "code": "255"},
    {"country": "Thailand", "code": "66"},
    {"country": "Timor-Leste", "code": "670"},
    {"country": "Togo", "code": "228"},
    {"country": "Tonga", "code": "676"},
    {"country": "Trinidad and Tobago", "code": "1868"},
    {"country": "Tunisia", "code": "216"},
    {"country": "Turkey", "code": "90"},
    {"country": "Turkmenistan", "code": "993"},
    {"country": "Tuvalu", "code": "688"},
    {"country": "Uganda", "code": "256"},
    {"country": "Ukraine", "code": "380"},
    {"country": "United Arab Emirates", "code": "971"},
    {"country": "United Kingdom", "code": "44"},
    {"country": "United States", "code": "1"},
    {"country": "Uruguay", "code": "598"},
    {"country": "Uzbekistan", "code": "998"},
    {"country": "Vanuatu", "code": "678"},
    {"country": "Vatican City", "code": "379"},
    {"country": "Venezuela", "code": "58"},
    {"country": "Vietnam", "code": "84"},
    {"country": "Yemen", "code": "967"},
    {"country": "Zambia", "code": "260"},
    {"country": "Zimbabwe", "code": "263"}
]
# 🌍 Global Function to Get World Mobile Codes Without +
def get_world_mobile_codes() -> list:
    """Return list of all world mobile codes without the + symbol."""
    return WORLD_MOBILE_CODES




def check_and_log_chat(
    db: Session,
    receiver_id: str,
    current_user: User
) -> bool:
    now = datetime.now(india_tz)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=india_tz)
    end_of_day = start_of_day + timedelta(days=1)

    # Normalize memtype (avoid mismatch)
    memtype = (current_user.memtype or "").strip().lower()

    # Set daily limits by memtype
    match memtype:
        case "free":
            daily_limit = 5
        case "basic_chat_pack":
            daily_limit = 10
        case "standard_pack":
            daily_limit = 20
        case "exclusive_pack":
            daily_limit = 5
        case _:
            # Allow unlimited for any other plan
            chat = ChatLog(sender_id=current_user.id, receiver_id=receiver_id, timestamp=now)
            db.add(chat)
            db.commit()
            return True

    # ✅ Clear old data before today
    db.query(ChatLog).filter(
        ChatLog.sender_id == current_user.id,
        ChatLog.timestamp < start_of_day
    ).delete()
    db.commit()

    # ✅ Get today's unique chats
    unique_receivers = db.query(ChatLog.receiver_id).filter(
        ChatLog.sender_id == current_user.id,
        ChatLog.timestamp >= start_of_day,
        ChatLog.timestamp < end_of_day
    ).distinct().all()

    receiver_ids_today = {r[0] for r in unique_receivers}

    # ✅ Already contacted → allow
    if receiver_id in receiver_ids_today:
        chat = ChatLog(sender_id=current_user.id, receiver_id=receiver_id, timestamp=now)
        db.add(chat)
        db.commit()
        return True

    # ✅ New user but under limit
    if len(receiver_ids_today) < daily_limit:
        chat = ChatLog(sender_id=current_user.id, receiver_id=receiver_id, timestamp=now)
        db.add(chat)
        db.commit()
        return True

    # ❌ Limit exceeded
    return False


#---badal-start

def filter_users(db: Session, search=None, status=None, plan=None, gender=None,
                 photo1=None, photo2=None, bio=None, expectation=None):

    query = db.query(User)

    # 🔍 Search across multiple fields
    if search:
        query = query.filter(or_(
            User.name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            User.phone.ilike(f"%{search}%")
        ))

    if status:
        query = query.filter(User.status == status)

    if plan:
        query = query.filter(User.plan == plan)

    if gender:
        query = query.filter(User.gender == gender)

    if photo1 is not None:
        query = query.filter(User.photo1.isnot(None) if photo1 else User.photo1.is_(None))

    if photo2 is not None:
        query = query.filter(User.photo2.isnot(None) if photo2 else User.photo2.is_(None))

    if bio is not None:
        query = query.filter(User.bio.isnot(None) if bio else User.bio.is_(None))

    if expectation:
        query = query.filter(User.expectation == expectation)

    return query.all()
