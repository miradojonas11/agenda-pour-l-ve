from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "agenda.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'admin' | 'prof' | 'student'
    full_name = Column(String, nullable=True)

    prof_matieres = relationship("Matiere", back_populates="professeur_obj")
    created_events = relationship("Evenement", back_populates="creator")
    created_devoirs = relationship("Devoir", back_populates="creator")
    attendances = relationship("Attendance", back_populates="user")
    messages_received = relationship("Message", back_populates="to_user", foreign_keys="Message.to_user_id")
    messages_sent = relationship("Message", back_populates="from_user", foreign_keys="Message.from_user_id")


class Classe(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)

    matieres = relationship("Matiere", back_populates="classe")


class Matiere(Base):
    __tablename__ = "matieres"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    professeur_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    salle = Column(String, nullable=True)
    couleur = Column(String, default="#3498db")
    classe_id = Column(Integer, ForeignKey("classes.id"), nullable=True)

    professeur_obj = relationship("User", back_populates="prof_matieres")
    classe = relationship("Classe", back_populates="matieres")
    evenements = relationship("Evenement", back_populates="matiere")
    devoirs = relationship("Devoir", back_populates="matiere")


class Evenement(Base):
    __tablename__ = "evenements"
    id = Column(Integer, primary_key=True, index=True)
    matiere_id = Column(Integer, ForeignKey("matieres.id"), nullable=False)
    date_debut = Column(DateTime, nullable=False)
    date_fin = Column(DateTime, nullable=False)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # nouvelle colonne : salle (peut être choisie par le prof pour chaque événement)
    salle = Column(String, nullable=True)

    matiere = relationship("Matiere", back_populates="evenements")
    creator = relationship("User", back_populates="created_events")
    attendances = relationship("Attendance", back_populates="evenement")


class Devoir(Base):
    __tablename__ = "devoirs"
    id = Column(Integer, primary_key=True, index=True)
    matiere_id = Column(Integer, ForeignKey("matieres.id"), nullable=False)
    titre = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    date_remise = Column(DateTime, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # informations du fichier attaché
    file_name = Column(String, nullable=True)  # nom d'origine du fichier
    file_path = Column(String, nullable=True)  # chemin local où est stocké le fichier

    matiere = relationship("Matiere", back_populates="devoirs")
    creator = relationship("User", back_populates="created_devoirs")


class Attendance(Base):
    __tablename__ = "attendances"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    evenement_id = Column(Integer, ForeignKey("evenements.id"), nullable=True)
    devoir_id = Column(Integer, ForeignKey("devoirs.id"), nullable=True)
    status = Column(String, nullable=False)  # 'yes' | 'no' | 'maybe'
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="attendances")
    evenement = relationship("Evenement", back_populates="attendances")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    subject = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    read = Column(Boolean, default=False)

    to_user = relationship("User", back_populates="messages_received", foreign_keys=[to_user_id])
    from_user = relationship("User", back_populates="messages_sent", foreign_keys=[from_user_id])


def init_db():
    Base.metadata.create_all(bind=engine)