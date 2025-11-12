import streamlit as st
import datetime
import calendar
import pandas as pd
import uuid
import os
from pathlib import Path
import io
import wave
import struct
import math

from agenda import crud
from agenda.db import SessionLocal

st.set_page_config(page_title="Agenda Multi-users", page_icon="📚", layout="wide")

# dossier de stockage des uploads
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def do_rerun():
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
        else:
            st.session_state["_need_rerun"] = True
            st.stop()
    except Exception:
        st.session_state["_need_rerun"] = True
        st.stop()


def check_rerun_flag():
    if st.session_state.get("_need_rerun"):
        st.session_state.pop("_need_rerun", None)
        try:
            if hasattr(st, "experimental_rerun"):
                st.experimental_rerun()
        except Exception:
            pass


def init_admin_if_missing(db):
    admins = db.query(crud.User).filter(crud.User.role == "admin").all()
    if not admins:
        crud.create_user(db, "admin", "admin123", "admin", full_name="Admin par défaut")


# --- utility: generate small beep WAV bytes (sine tone) ---
def generate_beep_wav(duration_s=0.15, freq=880.0, volume=0.5, sample_rate=22050):
    """
    Génère un court wav (bytes) contenant une sinusoïde.
    Utilisé pour la notification sonore.
    """
    num_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    # prepare raw frames in bytes
    frames = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        sample = volume * math.sin(2 * math.pi * freq * t)
        # 16-bit PCM
        val = int(sample * 32767.0)
        frames += struct.pack('<h', val)

    # write a proper WAV file
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    buf.seek(0)
    return buf.read()


# ---------- Auth / forms ----------
def login_form(db):
    with st.form("login_form"):
        st.subheader("Connexion")
        username = st.text_input("Nom d'utilisateur", key="login_user")
        password = st.text_input("Mot de passe", type="password", key="login_pwd")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            user = crud.authenticate_user(db, username, password)
            if user:
                st.session_state.user_id = user.id
                st.session_state.user_role = user.role
                st.session_state.username = user.username
                st.session_state.view = "home"
                do_rerun()
            else:
                st.error("Identifiants incorrects")


def register_user_form(db, role="student"):
    username = st.text_input(f"Nom d'utilisateur ({role})", key=f"reg_{role}_user")
    password = st.text_input("Mot de passe", type="password", key=f"reg_{role}_pwd")
    full_name = st.text_input("Nom complet", key=f"reg_{role}_name")
    if st.button(f"Créer {role}"):
        if username and password:
            existing = crud.get_user_by_username(db, username)
            if existing:
                st.error("Utilisateur déjà existant")
            else:
                crud.create_user(db, username, password, role, full_name=full_name)
                st.success(f"Utilisateur {username} créé avec rôle {role}")
                do_rerun()


# helpers events/devoirs/csv
def events_for_date(db, date_obj: datetime.date):
    return crud.list_evenements_for_date(db, date_obj)


def events_for_week(db, reference_date: datetime.datetime):
    debut_semaine = reference_date - datetime.timedelta(days=reference_date.weekday())
    week = []
    for i in range(7):
        jour = debut_semaine + datetime.timedelta(days=i)
        evs = events_for_date(db, jour.date())
        week.append({"date": jour, "evenements": sorted(evs, key=lambda x: x.date_debut)})
    return week


def events_for_month(db, year: int, month: int):
    cal = calendar.monthcalendar(year, month)
    events_mois = {}
    for semaine in cal:
        for day in semaine:
            if day != 0:
                date = datetime.date(year, month, day)
                events_mois[day] = events_for_date(db, date)
    return events_mois


def search_events(db, query: str):
    q = query.lower()
    all_events = db.query(crud.Evenement).join(crud.Matiere).join(crud.User, isouter=True).all()
    results = []
    for e in all_events:
        mat = e.matiere
        prof = mat.professeur_obj.username if mat.professeur_obj else ""
        if q in (mat.nom or "").lower() or q in (prof or "").lower() or q in (e.description or "").lower():
            results.append(e)
    return results


def export_events_csv_for_user(db, user_id: int):
    # export events visible to the user (for now all events); you can restrict by class later
    events = crud.list_evenements_all(db)
    if not events:
        return None
    rows = []
    for e in events:
        rows.append({
            "Matière": e.matiere.nom,
            "Professeur": e.matiere.professeur_obj.username if e.matiere.professeur_obj else "",
            "Salle": e.salle or e.matiere.salle or "",
            "Date Début": e.date_debut.strftime("%Y-%m-%d %H:%M"),
            "Date Fin": e.date_fin.strftime("%Y-%m-%d %H:%M"),
            "Description": e.description or ""
        })
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode('utf-8')


def main():
    db = SessionLocal()
    try:
        init_admin_if_missing(db)
        check_rerun_flag()

        st.session_state.setdefault("user_id", None)
        st.session_state.setdefault("user_role", None)
        st.session_state.setdefault("username", None)
        st.session_state.setdefault("view", "home")

        if st.session_state.user_id is None:
            st.title("📚 Agenda - Connexion")
            login_form(db)
            st.markdown("---")
            st.info("Si vous n'avez pas de compte, demandez à un administrateur. Un admin par défaut a été créé (admin/admin123).")
            return

        user_id = st.session_state.user_id
        role = st.session_state.user_role
        username = st.session_state.username

        # Sidebar: Accueil, Notifications, Logout
        st.sidebar.title(f"{username} ({role})")
        if st.sidebar.button("Accueil"):
            st.session_state.view = "home"
            do_rerun()

        # Notifications (anciennement Messages) preview
        notifs = crud.list_messages_for_user(db, user_id)
        unread = sum(1 for m in notifs if not m.read)
        if st.sidebar.button(f"Notifications ({unread})"):
            st.session_state.view = "notifications"
            do_rerun()

        if st.sidebar.button("Se déconnecter"):
            st.session_state.user_id = None
            st.session_state.user_role = None
            st.session_state.username = None
            st.session_state.view = "home"
            do_rerun()

        # if home, show banner
        if st.session_state.view == "home":
            st.header(f"Bienvenue, {username} ({role})")
            st.markdown("Utilisez la barre latérale pour accéder aux Notifications ou retourner à l'accueil.")
            st.markdown("---")

        # ADMIN (unchanged visual)
        if role == "admin":
            st.header("🔧 Panneau Admin")
            colA, colB = st.columns([2, 1])

            with colA:
                st.subheader("📂 Classes")
                with st.form("create_classe"):
                    nom = st.text_input("Nom de la classe", key="admin_classe_nom")
                    desc = st.text_area("Description", key="admin_classe_desc")
                    if st.form_submit_button("Créer la classe"):
                        crud.create_classe(db, nom, desc)
                        st.success("Classe créée")
                        crud.notify_students(db, "Nouvelle classe créée", f"La classe {nom} a été créée par {username}", from_user_id=user_id)
                        do_rerun()

                st.markdown("**Liste des classes**")
                for cl in crud.list_classes(db):
                    st.markdown(f"<div style='padding:10px;border-radius:8px;background:#f7f9fc'><strong>{cl.nom}</strong><br><small>{cl.description or ''}</small></div>", unsafe_allow_html=True)

                st.markdown("---")
                st.subheader("👥 Utilisateurs")
                with st.expander("Créer Professeur"):
                    register_user_form(db, role="prof")
                with st.expander("Créer Élève"):
                    register_user_form(db, role="student")

                st.markdown("---")
                st.subheader("📚 Matières")
                with st.form("create_matiere_form"):
                    nom = st.text_input("Nom Matière", key="admin_mat_nom")
                    profs = db.query(crud.User).filter(crud.User.role == "prof").all()
                    prof_options = [f"{p.id}:{p.username}" for p in profs]
                    prof_sel = st.selectbox("Professeur (optionnel)", [""] + prof_options, key="admin_mat_prof")
                    prof_id = int(prof_sel.split(":")[0]) if prof_sel else None
                    classes = crud.list_classes(db)
                    class_options = [f"{c.id}:{c.nom}" for c in classes]
                    class_sel = st.selectbox("Classe (optionnel)", [""] + class_options, key="admin_mat_class")
                    classe_id = int(class_sel.split(":")[0]) if class_sel else None
                    salle = st.text_input("Salle", key="admin_mat_salle")
                    couleur = st.color_picker("Couleur", "#3498db", key="admin_mat_color")
                    if st.form_submit_button("Créer Matière"):
                        crud.create_matiere(db, nom, prof_id, salle, couleur, classe_id)
                        st.success("Matière créée")
                        crud.notify_students(db, "Nouvelle matière", f"La matière {nom} a été créée", from_user_id=user_id)
                        do_rerun()

            with colB:
                st.subheader("Résumé")
                users = db.query(crud.User).all()
                st.metric("Utilisateurs", len(users))
                classes = crud.list_classes(db)
                st.metric("Classes", len(classes))
                matieres = crud.list_matieres(db)
                st.metric("Matières", len(matieres))

                st.markdown("---")
                st.subheader("Matières existantes")
                for m in matieres:
                    prof_name = m.professeur_obj.username if m.professeur_obj else "—"
                    classe_name = m.classe.nom if m.classe else "—"
                    st.markdown(f"<div style='padding:10px;border-radius:8px;background:#fff8e1;'><strong>{m.nom}</strong><br>Prof: {prof_name} — Classe: {classe_name}</div>", unsafe_allow_html=True)
                    if st.button(f"Supprimer {m.id}", key=f"admin_del_mat_{m.id}"):
                        crud.delete_matiere(db, m.id)
                        do_rerun()

        # PROF : choose salle per event + see attendees answers (detailed)
        elif role == "prof":
            st.header("🧑‍🏫 Panneau Professeur")
            st.subheader("Mes matières et actions")
            my_matieres = db.query(crud.Matiere).filter(crud.Matiere.professeur_id == user_id).all()

            if my_matieres:
                for m in my_matieres:
                    st.markdown(f"<div style='background:{m.couleur}20;padding:12px;border-radius:10px;border-left:6px solid {m.couleur};'><h4>📘 {m.nom}</h4><p>🏫 {m.salle or '—'}</p></div>", unsafe_allow_html=True)
                    cols = st.columns([2, 1])
                    with cols[0]:
                        with st.expander("Ajouter événement"):
                            date = st.date_input("Date", value=datetime.datetime.now().date(), key=f"ev_date_{m.id}")
                            hdeb = st.time_input("Heure début", value=datetime.time(9, 0), key=f"ev_deb_{m.id}")
                            hfin = st.time_input("Heure fin", value=datetime.time(10, 0), key=f"ev_fin_{m.id}")
                            desc = st.text_input("Description", key=f"ev_desc_{m.id}")
                            # salle choisie pour cet événement (par le prof)
                            salle_evt = st.text_input("Salle pour ce cours (écrivez ou laissez vide)", value=m.salle or "", key=f"ev_salle_{m.id}")
                            if st.button("Ajouter événement", key=f"add_ev_{m.id}"):
                                dt_deb = datetime.datetime.combine(date, hdeb)
                                dt_fin = datetime.datetime.combine(date, hfin)
                                ev = crud.add_evenement(db, m.id, dt_deb, dt_fin, desc, creator_id=user_id, salle=salle_evt or None)
                                crud.notify_students(db, f"Nouveau cours: {m.nom}", f"Un nouveau cours pour {m.nom} a été ajouté: {dt_deb.strftime('%Y-%m-%d %H:%M')} (Salle: {salle_evt or m.salle or '—'})", from_user_id=user_id)
                                st.success("Événement ajouté et notification envoyée")
                                do_rerun()

                        with st.expander("Ajouter devoir (avec fichier)"):
                            titre = st.text_input("Titre", key=f"dv_titre_{m.id}")
                            desc = st.text_area("Description", key=f"dv_desc_{m.id}")
                            date_remise = st.date_input("Date de remise (optionnel)", key=f"dv_date_{m.id}")
                            uploaded_file = st.file_uploader("Fichier (optionnel)", key=f"dv_file_{m.id}")
                            if st.button("Ajouter devoir", key=f"add_dv_{m.id}"):
                                dt_rem = None
                                if date_remise:
                                    dt_rem = datetime.datetime.combine(date_remise, datetime.time(23, 59))
                                file_name = None
                                file_path = None
                                if uploaded_file is not None:
                                    unique_name = f"{uuid.uuid4().hex}_{uploaded_file.name}"
                                    target_path = UPLOADS_DIR / unique_name
                                    with open(target_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    file_name = uploaded_file.name
                                    file_path = str(target_path)
                                d = crud.add_devoir(db, m.id, titre, desc, dt_rem, creator_id=user_id, file_name=file_name, file_path=file_path)
                                crud.notify_students(db, f"Nouveau devoir: {titre}", f"Un nouveau devoir pour {m.nom} a été publié: {titre}", from_user_id=user_id)
                                st.success("Devoir ajouté et notification envoyée")
                                do_rerun()
                    with cols[1]:
                        st.markdown("**Cours & Devoirs récents**")
                        evs = crud.list_evenements_for_matiere(db, m.id)
                        if evs:
                            for e in evs[:10]:
                                atts = crud.get_attendance_for_event(db, e.id)
                                counts = {"yes": 0, "no": 0, "maybe": 0}
                                for a in atts:
                                    counts[a.status] = counts.get(a.status, 0) + 1
                                st.write(f"- {e.date_debut.strftime('%Y-%m-%d %H:%M')} → {e.date_fin.strftime('%H:%M')}: {e.description or '—'} (Salle: {e.salle or m.salle or '—'})")
                                st.write(f"  Réponses: ✅{counts['yes']} ❌{counts['no']} ❓{counts['maybe']}")
                                if atts:
                                    st.markdown("  Détails:")
                                    for a in atts:
                                        usr = db.get(crud.User, a.user_id)
                                        st.write(f"    - {usr.username} : {a.status}")
                        else:
                            st.write("Aucun événement")
                        dvs = crud.list_devoirs_for_matiere(db, m.id)
                        if dvs:
                            for d in dvs[:10]:
                                st.write(f"- {d.titre} (remise: {d.date_remise.strftime('%Y-%m-%d') if d.date_remise else '—'})")
                                atts_d = crud.get_attendance_for_devoir(db, d.id)
                                counts_d = {"yes": 0, "no": 0, "maybe": 0}
                                for a in atts_d:
                                    counts_d[a.status] = counts_d.get(a.status, 0) + 1
                                st.write(f"  Réponses: ✅{counts_d['yes']} ❌{counts_d['no']} ❓{counts_d['maybe']}")
                                if atts_d:
                                    st.markdown("  Détails:")
                                    for a in atts_d:
                                        usr = db.get(crud.User, a.user_id)
                                        st.write(f"    - {usr.username} : {a.status}")
                                if d.file_path:
                                    try:
                                        with open(d.file_path, "rb") as f:
                                            bytesf = f.read()
                                        st.download_button(label=f"Télécharger {d.file_name}", data=bytesf, file_name=d.file_name)
                                    except Exception as ex:
                                        st.error("Erreur lecture fichier: " + str(ex))
                        else:
                            st.write("Aucun devoir")
            else:
                st.info("Vous n'avez pas encore de matières assignées. Contactez un administrateur.")

        # STUDENT
        elif role == "student":
            st.header("👩‍🎓 Espace Élève — Emploi du temps & Devoirs")
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📅 Vue Semaine", "📋 Vue Jour", "📚 Matières & Devoirs", "🗓️ Vue Mois", "🔍 Recherche"])

            # quick commands + CSV export
            col_nav1, col_nav2, col_nav3 = st.columns([1,1,2])
            with col_nav1:
                if st.button("📅 Aujourd'hui", key="stu_today"):
                    st.session_state.setdefault("stu_date_courante", datetime.datetime.now())
                    st.session_state["stu_date_courante"] = datetime.datetime.now()
                    do_rerun()
            with col_nav2:
                if st.button("🔄 Actualiser", key="stu_refresh"):
                    do_rerun()
            with col_nav3:
                csv_bytes = export_events_csv_for_user(db, user_id)
                if csv_bytes:
                    st.download_button("Télécharger mon emploi du temps (CSV)", data=csv_bytes, file_name="emploi_du_temps.csv", mime="text/csv")

            if 'stu_date_courante' not in st.session_state:
                st.session_state['stu_date_courante'] = datetime.datetime.now()

            # Week view with RSVP (radio + submit)
            with tab1:
                st.header("🗓️ Emploi du temps de la semaine")
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    if st.button("◀ Semaine précédente", key="stu_prev_week"):
                        st.session_state['stu_date_courante'] -= datetime.timedelta(weeks=1)
                        do_rerun()
                with col2:
                    date_courante = st.session_state['stu_date_courante']
                    debut_semaine = date_courante - datetime.timedelta(days=date_courante.weekday())
                    fin_semaine = debut_semaine + datetime.timedelta(days=6)
                    st.subheader(f"📅 Semaine du {debut_semaine.strftime('%d/%m/%Y')} au {fin_semaine.strftime('%d/%m/%Y')}")
                with col3:
                    if st.button("Semaine suivante ▶", key="stu_next_week"):
                        st.session_state['stu_date_courante'] += datetime.timedelta(weeks=1)
                        do_rerun()

                evenements_semaine = events_for_week(db, st.session_state['stu_date_courante'])
                cols = st.columns(7)
                jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
                for i, col in enumerate(cols):
                    with col:
                        jour_data = evenements_semaine[i]
                        st.subheader(f"**{jours[i]}**\n{jour_data['date'].strftime('%d/%m')}")
                        if jour_data['evenements']:
                            for event in jour_data['evenements']:
                                att = crud.get_user_attendance_for_event(db, user_id, event.id)
                                user_status = att.status if att else None
                                with st.container():
                                    st.markdown(
                                        f"""
                                        <div style='background-color: {event.matiere.couleur}20; 
                                                    padding: 12px; border-radius: 8px; 
                                                    border-left: 5px solid {event.matiere.couleur};
                                                    margin: 8px 0; font-size: 0.9em;'>
                                            <strong>🕒 {event.date_debut.strftime('%H:%M')}-{event.date_fin.strftime('%H:%M')}</strong><br>
                                            <strong>{event.matiere.nom}</strong><br>
                                            👨‍🏫 {event.matiere.professeur_obj.username if event.matiere.professeur_obj else '—'}<br>
                                            🏫 {event.salle or event.matiere.salle or '—'}
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )
                                    # nicer RSVP: radio + submit (more compact/consistent)
                                    key_base = f"rsvp_{event.id}"
                                    choice = st.radio("Réponse", options=["", "J'y vais", "Je n'y vais pas", "Peut-être"], index=0, key=key_base+"_radio", label_visibility="collapsed")
                                    if st.button("Envoyer réponse", key=key_base+"_submit"):
                                        mapping = {"J'y vais": "yes", "Je n'y vais pas": "no", "Peut-être": "maybe", "": "maybe"}
                                        sel = mapping.get(choice, "maybe")
                                        crud.set_attendance(db, user_id, event.id, sel)
                                        do_rerun()
                                    if user_status:
                                        st.caption(f"Votre réponse actuelle: {user_status}")
                        else:
                            st.info("Aucun cours")

            # Day view (with RSVP radio + submit)
            with tab2:
                st.header("📋 Emploi du temps du jour")
                date_jour = st.date_input("Sélectionnez une date", value=datetime.datetime.now().date(), key="stu_date_jour_selector")
                evenements_jour = events_for_date(db, date_jour)
                st.subheader(f"📅 {date_jour.strftime('%A %d %B %Y')}")
                if evenements_jour:
                    for idx, event in enumerate(sorted(evenements_jour, key=lambda x: x.date_debut)):
                        att = crud.get_user_attendance_for_event(db, user_id, event.id)
                        user_status = att.status if att else None
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(
                                    f"""
                                    <div style='background-color: {event.matiere.couleur}30; 
                                                padding: 20px; border-radius: 10px; 
                                                border-left: 8px solid {event.matiere.couleur};
                                                margin: 15px 0;'>
                                        <h4>📚 {event.matiere.nom}</h4>
                                        <p>🕒 <strong>Horaire:</strong> {event.date_debut.strftime('%H:%M')} - {event.date_fin.strftime('%H:%M')}</p>
                                        <p>👨‍🏫 <strong>Professeur:</strong> {event.matiere.professeur_obj.username if event.matiere.professeur_obj else '—'}</p>
                                        <p>🏫 <strong>Salle:</strong> {event.salle or event.matiere.salle or '—'}</p>
                                        <p>📝 <strong>Description:</strong> {event.description or 'Aucune description'}</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            with col2:
                                keyb = f"day_rsvp_{event.id}"
                                choice = st.radio("Réponse", options=["", "J'y vais", "Je n'y vais pas", "Peut-être"], key=keyb+"_radio", label_visibility="collapsed")
                                if st.button("Envoyer", key=keyb+"_submit"):
                                    mapping = {"J'y vais": "yes", "Je n'y vais pas": "no", "Peut-être": "maybe", "": "maybe"}
                                    sel = mapping.get(choice, "maybe")
                                    crud.set_attendance(db, user_id, event.id, sel)
                                    do_rerun()
                                if user_status:
                                    st.caption(f"Votre réponse: {user_status}")
                    st.metric("Nombre de cours aujourd'hui", len(evenements_jour))
                else:
                    st.info("🎉 Aucun cours prévu pour cette date !")

            # Matières & Devoirs (with RSVP for devoirs + download)
            with tab3:
                st.header("📚 Matières & Devoirs")
                matieres = crud.list_matieres(db)
                if matieres:
                    st.metric("Nombre total de matières", len(matieres))
                    for matiere in matieres:
                        with st.container():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(
                                    f"""
                                    <div style='background-color: {matiere.couleur}30; 
                                                padding: 15px; border-radius: 8px; 
                                                border-left: 6px solid {matiere.couleur};
                                                margin: 10px 0;'>
                                        <h4>📖 {matiere.nom}</h4>
                                        <p>👨‍🏫 <strong>Professeur:</strong> {matiere.professeur_obj.username if matiere.professeur_obj else '—'}</p>
                                        <p>🏫 <strong>Salle:</strong> {matiere.salle or '—'}</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            with col2:
                                if st.button("Voir détails", key=f"view_matiere_{matiere.id}"):
                                    st.session_state["view_matiere_id"] = matiere.id
                                    do_rerun()

                    # selected matiere details
                    if 'view_matiere_id' in st.session_state:
                        mid = st.session_state['view_matiere_id']
                        selected = db.get(crud.Matiere, mid)
                        if selected:
                            st.markdown("---")
                            st.subheader(f"Détails de la matière: {selected.nom}")
                            st.write(f"Professeur: {selected.professeur_obj.username if selected.professeur_obj else '—'}")
                            st.write(f"Salle: {selected.salle or '—'}")
                            st.write("Cours à venir :")
                            evs = crud.list_evenements_for_matiere(db, selected.id)
                            if evs:
                                for e in evs:
                                    st.write(f"- {e.date_debut.strftime('%Y-%m-%d %H:%M')} → {e.date_fin.strftime('%H:%M')} — {e.description or '—'} (Salle: {e.salle or selected.salle or '—'})")
                            else:
                                st.info("Aucun cours programmé pour cette matière.")
                            st.write("Devoirs :")
                            devoirs = crud.list_devoirs_for_matiere(db, selected.id)
                            if devoirs:
                                for d in devoirs:
                                    st.write(f"- {d.titre} — remise: {d.date_remise.strftime('%Y-%m-%d') if d.date_remise else '—'} — {d.description or '—'}")
                                    att_d = crud.get_user_attendance_for_devoir(db, user_id, d.id)
                                    user_status_d = att_d.status if att_d else None
                                    keybase = f"dv_rsvp_{d.id}"
                                    choice = st.radio("Choix", options=["", "Je ferai", "Je ne ferai pas", "Peut-être"], key=keybase+"_radio", label_visibility="collapsed")
                                    if st.button("Envoyer", key=keybase+"_submit"):
                                        mapping = {"Je ferai": "yes", "Je ne ferai pas": "no", "Peut-être": "maybe", "": "maybe"}
                                        sel = mapping.get(choice, "maybe")
                                        crud.set_attendance(db, user_id, None, sel, devoir_id=d.id)
                                        do_rerun()
                                    if user_status_d:
                                        st.caption(f"Votre réponse: {user_status_d}")
                                    if d.file_path:
                                        try:
                                            with open(d.file_path, "rb") as f:
                                                file_bytes = f.read()
                                            st.download_button(label=f"Télécharger: {d.file_name}", data=file_bytes, file_name=d.file_name)
                                        except Exception as ex:
                                            st.error(f"Erreur lecture fichier: {ex}")
                            else:
                                st.info("Aucun devoir pour cette matière.")
                else:
                    st.info("📝 Aucune matière ajoutée pour le moment")

            # Month view (unchanged)
            with tab4:
                st.header("🗓️ Vue Mensuelle")
                today = datetime.datetime.now()
                annee = st.number_input("Année", min_value=2000, max_value=2100, value=today.year, key="stu_annee_mois")
                mois = st.selectbox("Mois", list(calendar.month_name)[1:], index=max(0, today.month - 1), key="stu_mois_select")
                mois_num = list(calendar.month_name).index(mois)
                evenements_mois = events_for_month(db, annee, mois_num)
                cal = calendar.monthcalendar(annee, mois_num)
                st.subheader(f"📅 {mois} {annee}")
                jours_semaine = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
                cols = st.columns(7)
                for i, col in enumerate(cols):
                    with col:
                        st.markdown(f"**{jours_semaine[i]}**")
                for semaine in cal:
                    cols = st.columns(7)
                    for i, jour in enumerate(semaine):
                        with cols[i]:
                            if jour != 0:
                                date_jour = datetime.date(annee, mois_num, jour)
                                evenements_du_jour = evenements_mois.get(jour, [])
                                today_str = today.strftime('%Y-%m-%d')
                                current_day_str = date_jour.strftime('%Y-%m-%d')
                                if today_str == current_day_str:
                                    st.markdown(f"<div style='background-color: #ffeb3b; padding: 5px; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;'><strong>{jour}</strong></div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<strong>{jour}</strong>", unsafe_allow_html=True)
                                if evenements_du_jour:
                                    st.markdown(f"<small>{len(evenements_du_jour)} cours</small>", unsafe_allow_html=True)
                                    for event in evenements_du_jour[:2]:
                                        st.markdown(f"<div style='background-color: {event.matiere.couleur}30; padding: 2px; margin: 1px; border-radius: 3px; font-size: 0.7em;'>{event.matiere.nom}</div>", unsafe_allow_html=True)
                                    if len(evenements_du_jour) > 2:
                                        st.markdown(f"<small>+{len(evenements_du_jour) - 2} de plus</small>", unsafe_allow_html=True)
                            else:
                                st.write("")

            # Search tab (unchanged)
            with tab5:
                st.header("🔍 Recherche d'événements")
                query = st.text_input("Rechercher un cours, professeur ou description")
                if query:
                    resultats = search_events(db, query)
                    if resultats:
                        st.success(f"🔍 {len(resultats)} résultat(s) trouvé(s) pour '{query}'")
                        for event in resultats:
                            with st.container():
                                st.markdown(f"<div style='background-color: {event.matiere.couleur}30; padding: 15px; border-radius: 8px; border-left: 6px solid {event.matiere.couleur}; margin: 10px 0;'><h4>📚 {event.matiere.nom}</h4><p>📅 <strong>Date:</strong> {event.date_debut.strftime('%d/%m/%Y')}</p><p>🕒 <strong>Horaire:</strong> {event.date_debut.strftime('%H:%M')} - {event.date_fin.strftime('%H:%M')}</p><p>👨‍🏫 <strong>Professeur:</strong> {event.matiere.professeur_obj.username if event.matiere.professeur_obj else '—'}</p><p>🏫 <strong>Salle:</strong> {event.salle or event.matiere.salle or '—'}</p><p>📝 <strong>Description:</strong> {event.description or 'Aucune description'}</p></div>", unsafe_allow_html=True)
                    else:
                        st.warning(f"❌ Aucun résultat trouvé pour '{query}'")

        else:
            st.error("Rôle inconnu")

        # Notifications view (formerly Messages) — sound + mark read
        if st.session_state.get("view") == "notifications":
            st.header("🔔 Notifications")
            messages = crud.list_messages_for_user(db, user_id)
            unread_msgs = [m for m in messages if not m.read]
            # play beep if there are unread notifications
            if unread_msgs:
                try:
                    beep = generate_beep_wav()
                    st.audio(beep, format="audio/wav")
                except Exception:
                    # ignore audio errors; still show notifications visually
                    pass
            if not messages:
                st.info("Aucune notification")
            else:
                for m in messages:
                    cols = st.columns([8,1])
                    with cols[0]:
                        st.markdown(f"**{m.subject}** — {m.created_at.strftime('%Y-%m-%d %H:%M')}")
                        st.write(m.content)
                    with cols[1]:
                        if not m.read:
                            if st.button("Marquer lu", key=f"mark_read_{m.id}"):
                                crud.mark_message_read(db, m.id)
                                do_rerun()
    finally:
        # always close DB session
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()