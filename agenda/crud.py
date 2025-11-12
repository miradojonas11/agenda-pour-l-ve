from typing import Optional, List, Generator, Dict
from sqlalchemy.orm import Session
from .db import (
    User, Classe, Matiere, Evenement, Devoir, Attendance, Message, SessionLocal, init_db
)
from passlib.hash import pbkdf2_sha256
# compat bcrypt handler (optionnel)
try:
    from passlib.hash import bcrypt as passlib_bcrypt
except Exception:
    passlib_bcrypt = None

import datetime
import os
import smtplib
from email.message import EmailMessage

# Initialize DB (safe to call multiple times)
init_db()


# ---------- Users ----------
def create_user(db: Session, username: str, password: str, role: str, full_name: Optional[str] = None) -> User:
    hashed = pbkdf2_sha256.hash(password)
    user = User(username=username, password_hash=hashed, role=role, full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    # Essayer pbkdf2_sha256
    try:
        if pbkdf2_sha256.verify(password, user.password_hash):
            return user
    except Exception:
        pass

    # Compatibilité bcrypt si présent
    if passlib_bcrypt is not None:
        try:
            if passlib_bcrypt.verify(password, user.password_hash):
                return user
        except Exception:
            pass

    return None


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


# ---------- Classes ----------
def create_classe(db: Session, nom: str, description: str = "") -> Classe:
    classe = Classe(nom=nom, description=description)
    db.add(classe)
    db.commit()
    db.refresh(classe)
    return classe


def list_classes(db: Session) -> List[Classe]:
    return db.query(Classe).order_by(Classe.nom).all()


# ---------- Matières ----------
def create_matiere(db: Session, nom: str, professeur_id: Optional[int], salle: str, couleur: str, classe_id: Optional[int]) -> Matiere:
    mat = Matiere(nom=nom, professeur_id=professeur_id, salle=salle, couleur=couleur, classe_id=classe_id)
    db.add(mat)
    db.commit()
    db.refresh(mat)
    return mat


def delete_matiere(db: Session, matiere_id: int) -> bool:
    mat = db.query(Matiere).get(matiere_id)
    if not mat:
        return False
    db.delete(mat)
    db.commit()
    return True


def list_matieres(db: Session) -> List[Matiere]:
    return db.query(Matiere).order_by(Matiere.nom).all()


# ---------- Evenements ----------
def add_evenement(db: Session, matiere_id: int, date_debut: datetime.datetime, date_fin: datetime.datetime, description: str, creator_id: Optional[int], salle: Optional[str] = None) -> Evenement:
    ev = Evenement(matiere_id=matiere_id, date_debut=date_debut, date_fin=date_fin, description=description, creator_id=creator_id, salle=salle)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_evenements_for_matiere(db: Session, matiere_id: int):
    return db.query(Evenement).filter(Evenement.matiere_id == matiere_id).order_by(Evenement.date_debut).all()


def list_evenements_for_date(db: Session, date: datetime.date):
    start = datetime.datetime.combine(date, datetime.time.min)
    end = datetime.datetime.combine(date, datetime.time.max)
    return db.query(Evenement).filter(Evenement.date_debut >= start, Evenement.date_debut <= end).order_by(Evenement.date_debut).all()


def list_evenements_all(db: Session):
    return db.query(Evenement).order_by(Evenement.date_debut).all()


# ---------- Devoirs ----------
def add_devoir(db: Session, matiere_id: int, titre: str, description: str, date_remise: Optional[datetime.datetime], creator_id: Optional[int], file_name: Optional[str] = None, file_path: Optional[str] = None) -> Devoir:
    d = Devoir(matiere_id=matiere_id, titre=titre, description=description, date_remise=date_remise, creator_id=creator_id, file_name=file_name, file_path=file_path)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def list_devoirs_for_matiere(db: Session, matiere_id: int):
    return db.query(Devoir).filter(Devoir.matiere_id == matiere_id).order_by(Devoir.date_remise).all()


def list_devoirs_all(db: Session) -> List[Devoir]:
    return db.query(Devoir).order_by(Devoir.date_remise).all()


# ---------- Attendance (RSVP) ----------
def set_attendance(db: Session, user_id: int, evenement_id: Optional[int], status: str, devoir_id: Optional[int] = None):
    """
    Set attendance for an event or a devoir.
    For events: pass evenement_id and devoir_id=None.
    For devoirs: pass devoir_id and evenement_id=None.
    status in {'yes','no','maybe'}
    """
    if evenement_id is None and devoir_id is None:
        raise ValueError("Either evenement_id or devoir_id must be provided")

    query = db.query(Attendance).filter(Attendance.user_id == user_id)
    if evenement_id is not None:
        query = query.filter(Attendance.evenement_id == evenement_id)
    else:
        query = query.filter(Attendance.devoir_id == devoir_id)

    att = query.first()
    if att:
        att.status = status
        att.updated_at = datetime.datetime.utcnow()
    else:
        att = Attendance(user_id=user_id, evenement_id=evenement_id, devoir_id=devoir_id, status=status)
        db.add(att)
    db.commit()
    db.refresh(att)
    return att


def get_attendance_for_event(db: Session, evenement_id: int) -> List[Attendance]:
    return db.query(Attendance).filter(Attendance.evenement_id == evenement_id).all()


def get_attendance_for_devoir(db: Session, devoir_id: int) -> List[Attendance]:
    return db.query(Attendance).filter(Attendance.devoir_id == devoir_id).all()


def get_user_attendance_for_event(db: Session, user_id: int, evenement_id: int) -> Optional[Attendance]:
    return db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.evenement_id == evenement_id).first()


def get_user_attendance_for_devoir(db: Session, user_id: int, devoir_id: int) -> Optional[Attendance]:
    return db.query(Attendance).filter(Attendance.user_id == user_id, Attendance.devoir_id == devoir_id).first()


# ---------- Messages / Notifications ----------
def create_message(db: Session, to_user_id: int, subject: str, content: str, from_user_id: Optional[int] = None) -> Message:
    msg = Message(to_user_id=to_user_id, from_user_id=from_user_id, subject=subject, content=content, created_at=datetime.datetime.utcnow(), read=False)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_messages_for_user(db: Session, user_id: int) -> List[Message]:
    return db.query(Message).filter(Message.to_user_id == user_id).order_by(Message.created_at.desc()).all()


def mark_message_read(db: Session, message_id: int):
    msg = db.query(Message).get(message_id)
    if msg:
        msg.read = True
        db.commit()
        db.refresh(msg)
        return True
    return False


def notify_students(db: Session, subject: str, content: str, from_user_id: Optional[int] = None):
    """
    Create internal messages (and optionally send email) to all students.
    """
    students = db.query(User).filter(User.role == "student").all()
    for s in students:
        create_message(db, s.id, subject, content, from_user_id=from_user_id)
        # try to send email if SMTP settings provided
        try:
            smtp_host = os.environ.get("SMTP_HOST")
            smtp_port = int(os.environ.get("SMTP_PORT", "0") or 0)
            smtp_user = os.environ.get("SMTP_USER")
            smtp_pass = os.environ.get("SMTP_PASS")
            from_addr = os.environ.get("SMTP_FROM", "no-reply@example.com")
            if smtp_host and smtp_port and smtp_user and smtp_pass:
                # send basic email (blocking)
                em = EmailMessage()
                em["Subject"] = subject
                em["From"] = from_addr
                em["To"] = s.username  # assumes username is email if you use SMTP
                em.set_content(content)
                with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
                    smtp.login(smtp_user, smtp_pass)
                    smtp.send_message(em)
        except Exception:
            # swallow exceptions — internal messages still created
            pass


# Helper to get DB session (use with `with` pattern in app)
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()