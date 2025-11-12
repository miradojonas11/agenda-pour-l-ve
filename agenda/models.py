from typing import Dict
import datetime


class Matiere:
    def __init__(self, nom: str, professeur: str, salle: str, couleur: str = "#3498db"):
        self.nom = nom
        self.professeur = professeur
        self.salle = salle
        self.couleur = couleur

    def to_dict(self) -> Dict:
        return {
            "nom": self.nom,
            "professeur": self.professeur,
            "salle": self.salle,
            "couleur": self.couleur
        }

    def __repr__(self):
        return f"Matiere(nom={self.nom!r}, professeur={self.professeur!r})"


class Evenement:
    def __init__(self, matiere: Matiere, date_debut: datetime.datetime,
                 date_fin: datetime.datetime, description: str = ""):
        self.matiere = matiere
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.description = description

    def to_dict(self) -> Dict:
        return {
            "matiere": self.matiere.to_dict(),
            "date_debut": self.date_debut.isoformat(),
            "date_fin": self.date_fin.isoformat(),
            "description": self.description
        }

    def __repr__(self):
        return f"Evenement(matiere={self.matiere.nom!r}, date_debut={self.date_debut!r})"