import json
import datetime
import calendar
from pathlib import Path
from typing import List, Dict, Optional

# import relatif pour éviter les cycles
from .models import Matiere, Evenement


class AgendaManager:
    def __init__(self, data_file: str = "agenda_data.json"):
        self.data_file = Path(data_file)
        self.evenements: List[Evenement] = []
        self.matieres: List[Matiere] = []
        self.charger_donnees()

    # Matières
    def ajouter_matiere(self, nom: str, professeur: str, salle: str, couleur: str) -> Matiere:
        matiere = Matiere(nom, professeur, salle, couleur)
        self.matieres.append(matiere)
        self.sauvegarder_donnees()
        return matiere

    def supprimer_matiere(self, index: int):
        if 0 <= index < len(self.matieres):
            matiere_a_supprimer = self.matieres[index]
            # Supprimer aussi les événements associés
            self.evenements = [e for e in self.evenements if e.matiere.nom != matiere_a_supprimer.nom]
            self.matieres.pop(index)
            self.sauvegarder_donnees()

    # Événements
    def ajouter_evenement(self, matiere: Matiere, date_debut: datetime.datetime,
                          date_fin: datetime.datetime, description: str) -> Evenement:
        evenement = Evenement(matiere, date_debut, date_fin, description)
        self.evenements.append(evenement)
        self.sauvegarder_donnees()
        return evenement

    def modifier_evenement(self, index: int, matiere: Optional[Matiere] = None,
                           date_debut: Optional[datetime.datetime] = None,
                           date_fin: Optional[datetime.datetime] = None,
                           description: Optional[str] = None):
        if 0 <= index < len(self.evenements):
            if matiere:
                self.evenements[index].matiere = matiere
            if date_debut:
                self.evenements[index].date_debut = date_debut
            if date_fin:
                self.evenements[index].date_fin = date_fin
            if description is not None:
                self.evenements[index].description = description
            self.sauvegarder_donnees()

    def supprimer_evenement(self, index: int):
        if 0 <= index < len(self.evenements):
            self.evenements.pop(index)
            self.sauvegarder_donnees()

    # Recherches / filtres
    def get_evenements_par_jour(self, date: datetime.datetime) -> List[Evenement]:
        return [e for e in self.evenements if e.date_debut.date() == date.date()]

    def get_evenements_semaine(self, date_reference: datetime.datetime) -> List[Dict]:
        debut_semaine = date_reference - datetime.timedelta(days=date_reference.weekday())
        evenements_semaine = []
        for i in range(7):
            jour = debut_semaine + datetime.timedelta(days=i)
            evenements_jour = self.get_evenements_par_jour(jour)
            evenements_semaine.append({
                "date": jour,
                "evenements": sorted(evenements_jour, key=lambda x: x.date_debut)
            })
        return evenements_semaine

    def get_evenements_mois(self, annee: int, mois: int) -> Dict[int, List[Evenement]]:
        evenements_mois: Dict[int, List[Evenement]] = {}
        cal = calendar.monthcalendar(annee, mois)
        for semaine in cal:
            for jour in semaine:
                if jour != 0:
                    date = datetime.datetime(annee, mois, jour)
                    evenements_mois[jour] = self.get_evenements_par_jour(date)
        return evenements_mois

    def rechercher_evenements(self, query: str) -> List[Evenement]:
        query_lower = query.lower()
        return [e for e in self.evenements if query_lower in e.matiere.nom.lower()
                or query_lower in e.matiere.professeur.lower()
                or query_lower in e.description.lower()]

    # Sauvegarde / Chargement
    def sauvegarder_donnees(self):
        data = {
            "matieres": [m.to_dict() for m in self.matieres],
            "evenements": [e.to_dict() for e in self.evenements]
        }
        try:
            with self.data_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            # Si tu veux logger, tu peux utiliser logging
            print("Erreur sauvegarde:", exc)

    def charger_donnees(self):
        try:
            if self.data_file.exists():
                with self.data_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                self.matieres = []
                self.evenements = []

                for matiere_data in data.get("matieres", []):
                    matiere = Matiere(
                        matiere_data["nom"],
                        matiere_data["professeur"],
                        matiere_data["salle"],
                        matiere_data.get("couleur", "#3498db")
                    )
                    self.matieres.append(matiere)

                for event_data in data.get("evenements", []):
                    matiere_data = event_data["matiere"]
                    # Trouver la matière correspondante
                    matiere_trouvee = None
                    for m in self.matieres:
                        if (m.nom == matiere_data["nom"] and
                                m.professeur == matiere_data["professeur"]):
                            matiere_trouvee = m
                            break

                    if matiere_trouvee:
                        evenement = Evenement(
                            matiere_trouvee,
                            datetime.datetime.fromisoformat(event_data["date_debut"]),
                            datetime.datetime.fromisoformat(event_data["date_fin"]),
                            event_data.get("description", "")
                        )
                        self.evenements.append(evenement)
        except Exception as exc:
            print("Erreur chargement:", exc)