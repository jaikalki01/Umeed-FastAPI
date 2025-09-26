from sqlalchemy.orm import Session

from app.models.models import Banner1, Banner2


# --- Banner1 ---
def create_banner1_with_file(db: Session, banner_name: str, banner_url: str | None):
    db_banner = Banner1(banner_name=banner_name, banner_url=banner_url)
    db.add(db_banner)
    db.commit()
    db.refresh(db_banner)
    return db_banner

def get_banner1(db: Session, banner_id: int):
    return db.query(Banner1).filter(Banner1.id == banner_id).first()

def get_all_banner1(db: Session):
    return db.query(Banner1).all()

def update_banner1_with_file(db: Session, banner_id: int, banner_name: str, banner_url: str | None):
    db_banner = get_banner1(db, banner_id)
    if db_banner:
        db_banner.banner_name = banner_name
        if banner_url:  # update only if new file provided
            db_banner.banner_url = banner_url
        db.commit()
        db.refresh(db_banner)
    return db_banner

def delete_banner1(banner_id: int,db: Session):
    db_banner = get_banner1(db, banner_id)
    if db_banner:
        db.delete(db_banner)
        db.commit()
    return db_banner


# --- Banner2 ---
def create_banner2_with_file(db: Session, banner_name: str, banner_url: str | None):
    db_banner = Banner2(banner_name=banner_name, banner_url=banner_url)
    db.add(db_banner)
    db.commit()
    db.refresh(db_banner)
    return db_banner

def get_banner2(db: Session, banner_id: int):
    return db.query(Banner2).filter(Banner2.id == banner_id).first()

def get_all_banner2(db: Session):
    return db.query(Banner2).all()

def update_banner2_with_file(db: Session, banner_id: int, banner_name: str, banner_url: str | None):
    db_banner = get_banner2(db, banner_id)
    if db_banner:
        db_banner.banner_name = banner_name
        if banner_url:
            db_banner.banner_url = banner_url
        db.commit()
        db.refresh(db_banner)
    return db_banner

def delete_banner2(db: Session,banner_id: int):
    db_banner = get_banner2(db, banner_id)
    if db_banner:
        db.delete(db_banner)
        db.commit()
    return db_banner
