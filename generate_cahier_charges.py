#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération du Cahier des Charges - SiraScol (Django + SQLite)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, ListFlowable, ListItem, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# Couleurs
PRIMARY = HexColor("#1a365d")      # Bleu foncé
SECONDARY = HexColor("#2b6cb0")    # Bleu
ACCENT = HexColor("#3182ce")       # Bleu clair
LIGHT_BG = HexColor("#ebf8ff")     # Fond clair
GRAY = HexColor("#4a5568")
LIGHT_GRAY = HexColor("#e2e8f0")
SUCCESS = HexColor("#276749")

def create_styles():
    styles = getSampleStyleSheet()

    # Titre principal
    styles.add(ParagraphStyle(
        name='MainTitle',
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        textColor=PRIMARY,
        spaceAfter=6
    ))

    # Sous-titre
    styles.add(ParagraphStyle(
        name='SubTitle',
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        textColor=GRAY,
        spaceAfter=4
    ))

    # Titre de section
    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=PRIMARY,
        spaceBefore=18,
        spaceAfter=8,
        borderPadding=3,
    ))

    # Sous-section
    styles.add(ParagraphStyle(
        name='SubSection',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=SECONDARY,
        spaceBefore=12,
        spaceAfter=6
    ))

    # Corps de texte
    styles.add(ParagraphStyle(
        name='BodyTextFR',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        alignment=TA_JUSTIFY,
        textColor=black,
        spaceAfter=6
    ))

    # Texte normal
    styles.add(ParagraphStyle(
        name='NormalFR',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
        textColor=black,
        spaceAfter=4
    ))

    # Item de liste
    styles.add(ParagraphStyle(
        name='ListItemFR',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        leftIndent=15,
        spaceAfter=2
    ))

    # Meta info
    styles.add(ParagraphStyle(
        name='MetaInfo',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=GRAY,
        spaceAfter=2
    ))

    # Footer
    styles.add(ParagraphStyle(
        name='Footer',
        fontName='Helvetica',
        fontSize=8,
        alignment=TA_CENTER,
        textColor=GRAY
    ))

    # Tableau header
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=white,
        alignment=TA_CENTER
    ))

    # Tableau cell
    styles.add(ParagraphStyle(
        name='TableCell',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=black
    ))

    # Code
    styles.add(ParagraphStyle(
        name='CodeStyle',
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=HexColor("#1a202c"),
        backColor=HexColor("#f7fafc"),
        leftIndent=10,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=4
    ))

    return styles


def add_header_footer(canvas, doc):
    canvas.saveState()
    page_width, page_height = A4

    # Header line
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(1.5)
    canvas.line(1.5*cm, page_height - 1.2*cm, page_width - 1.5*cm, page_height - 1.2*cm)

    # Header text
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(1.5*cm, page_height - 1*cm, "Cahier des Charges – SiraScol (Django + SQLite)")
    canvas.drawRightString(page_width - 1.5*cm, page_height - 1*cm, "Version 1.1")

    # Footer
    canvas.setStrokeColor(LIGHT_GRAY)
    canvas.setLineWidth(0.8)
    canvas.line(1.5*cm, 1.3*cm, page_width - 1.5*cm, 1.3*cm)

    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(page_width / 2, 0.8*cm, f"Page {doc.page}")

    canvas.restoreState()


def create_table(data, col_widths, styles):
    """Crée un tableau stylé"""
    formatted_data = []
    for i, row in enumerate(data):
        formatted_row = []
        for cell in row:
            if i == 0:
                formatted_row.append(Paragraph(str(cell), styles['TableHeader']))
            else:
                formatted_row.append(Paragraph(str(cell), styles['TableCell']))
        formatted_data.append(formatted_row)

    table = Table(formatted_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table


def build_pdf():
    output_path = "/home/workdir/artifacts/Cahier_des_Charges_Gestion_Scolaire_Django_SQLite.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.8*cm,
        bottomMargin=1.8*cm
    )

    styles = create_styles()
    story = []

    # ========== PAGE DE GARDE ==========
    story.append(Spacer(1, 2.5*cm))
    story.append(Paragraph("CAHIER DES CHARGES", styles['MainTitle']))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="60%", thickness=2, color=PRIMARY, spaceBefore=5, spaceAfter=5, hAlign='CENTER'))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Application Web de SiraScol", styles['MainTitle']))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Développée avec <b>Django 5.x</b> + <b>SQLite</b>", styles['SubTitle']))
    story.append(Spacer(1, 1.2*cm))

    # Infos projet
    info_data = [
        ["Version", "1.1"],
        ["Date", "21 septembre 2026"],
        ["Projet", "School Management System (SMS)"],
        ["Base de données", "SQLite"],
        ["Frontend recommandé", "Django Templates + HTMX + Tailwind CSS"],
        ["Public cible", "Collège / Lycée / Établissement privé ou public"],
    ]

    info_table = Table(
        [[Paragraph(f"<b>{k}</b>", styles['NormalFR']), Paragraph(v, styles['NormalFR'])] for k, v in info_data],
        colWidths=[5*cm, 10*cm]
    )
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_BG),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)

    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("Document de spécifications fonctionnelles et techniques", styles['MetaInfo']))
    story.append(Paragraph("Prêt à servir de base contractuelle ou de roadmap de développement", styles['MetaInfo']))

    story.append(PageBreak())

    # ========== 1. PRÉSENTATION ==========
    story.append(Paragraph("1. Présentation du projet", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph(
        "L’application vise à digitaliser et centraliser l’ensemble des processus de gestion d’un établissement scolaire "
        "(collège, lycée ou établissement privé/public de taille petite à moyenne). Elle permet de gérer les élèves, "
        "les enseignants, les classes, les notes, les absences, les emplois du temps, les frais de scolarité, "
        "les communications et le reporting administratif.",
        styles['BodyTextFR']
    ))
    story.append(Paragraph(
        "L’objectif principal est de remplacer les processus manuels (Excel, cahiers, papiers) par une solution "
        "centralisée, sécurisée, multi-rôles et accessible via navigateur (desktop + responsive mobile).",
        styles['BodyTextFR']
    ))
    story.append(Paragraph(
        "Cette version du cahier des charges est <b>spécifiquement adaptée à SQLite</b> comme système de gestion "
        "de base de données, ce qui simplifie grandement le déploiement et la maintenance pour un établissement "
        "de taille classique.",
        styles['BodyTextFR']
    ))

    # ========== 2. OBJECTIFS ==========
    story.append(Paragraph("2. Objectifs", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("Objectifs métier", styles['SubSection']))
    objectifs_metier = [
        "Centraliser toutes les données scolaires (élèves, notes, absences, paiements…).",
        "Réduire le temps administratif des secrétaires, enseignants et direction.",
        "Améliorer la communication entre l’école, les parents et les élèves.",
        "Fournir des tableaux de bord et rapports en temps réel.",
        "Garantir la traçabilité et la conformité (RGPD / protection des données)."
    ]
    for obj in objectifs_metier:
        story.append(Paragraph(f"• {obj}", styles['ListItemFR']))

    story.append(Paragraph("Objectifs techniques", styles['SubSection']))
    objectifs_tech = [
        "Application web robuste, maintenable et évolutive basée sur Django 5.x.",
        "Utilisation de SQLite pour simplifier l’installation et les sauvegardes.",
        "Interface intuitive et responsive (mobile-first).",
        "Architecture claire en apps Django séparées.",
        "Possibilité d’évolution vers PostgreSQL si le besoin de scalabilité apparaît."
    ]
    for obj in objectifs_tech:
        story.append(Paragraph(f"• {obj}", styles['ListItemFR']))

    # ========== 3. PÉRIMÈTRE ==========
    story.append(Paragraph("3. Périmètre du projet", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("Inclus (MVP + extensions)", styles['SubSection']))
    inclus = [
        "Gestion des utilisateurs et rôles",
        "Gestion des élèves, enseignants, parents",
        "Gestion des classes, niveaux, matières et années scolaires",
        "Emploi du temps",
        "Notes et bulletins (PDF)",
        "Absences et retards",
        "Frais de scolarité et paiements",
        "Communication (annonces + messagerie simple)",
        "Tableaux de bord et reporting",
        "Administration système"
    ]
    for item in inclus:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    story.append(Paragraph("Hors périmètre (version 1)", styles['SubSection']))
    hors = [
        "Application mobile native (possible via API plus tard)",
        "Module de cantine avancé / gestion de stock",
        "Module de bibliothèque complet",
        "Multi-établissement (extensible ultérieurement)",
        "Paiements en ligne complets (Stripe, PayPal…)"
    ]
    for item in hors:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 4. ACTEURS ==========
    story.append(Paragraph("4. Acteurs et rôles", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    roles_data = [
        ["Rôle", "Description", "Accès principaux"],
        ["Super Admin", "Administrateur technique", "Tout + configuration système"],
        ["Directeur", "Direction de l’établissement", "Tableaux de bord, validations, rapports"],
        ["Secrétaire / Admin", "Gestion administrative quotidienne", "Élèves, inscriptions, paiements, absences"],
        ["Enseignant", "Professeur", "Notes, absences, emploi du temps, classes"],
        ["Parent", "Parent / tuteur légal", "Notes, absences, paiements, messages"],
        ["Élève", "Élève", "Notes, emploi du temps, messages"],
    ]
    story.append(create_table(roles_data, [3.2*cm, 5.5*cm, 7.3*cm], styles))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Authentification : Django Auth + permissions par groupes. Possibilité d’ajouter django-guardian "
        "pour des permissions au niveau objet si nécessaire.",
        styles['BodyTextFR']
    ))

    # ========== 5. FONCTIONNALITÉS ==========
    story.append(Paragraph("5. Fonctionnalités détaillées", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    # 5.1
    story.append(Paragraph("5.1 Gestion des utilisateurs et authentification", styles['SubSection']))
    for item in [
        "Connexion / déconnexion / mot de passe oublié",
        "Création et gestion des comptes uniquement par l’administration",
        "Gestion des rôles et permissions (Groupes Django)",
        "Profil utilisateur (photo, coordonnées, informations de contact)",
        "Journal d’activité (logs de connexion et actions importantes)"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.2
    story.append(Paragraph("5.2 Gestion des élèves", styles['SubSection']))
    for item in [
        "Création, modification et archivage d’un élève",
        "Informations personnelles + scolaires (matricule, date d’entrée, statut)",
        "Affectation à une classe / niveau / année scolaire",
        "Dossier scolaire avec upload de documents",
        "Historique des classes précédentes",
        "Recherche avancée et filtres (classe, statut, année…)"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.3
    story.append(Paragraph("5.3 Gestion des enseignants", styles['SubSection']))
    for item in [
        "Création et gestion des profils enseignants",
        "Affectation des matières et des classes",
        "Suivi de la charge horaire",
        "Gestion des disponibilités"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.4
    story.append(Paragraph("5.4 Structure pédagogique", styles['SubSection']))
    for item in [
        "Gestion des années scolaires (ouverture / clôture)",
        "Niveaux (6ème, 5ème… ou CP, CE1… selon le type d’établissement)",
        "Classes (ex. : 6ème A, Terminale S1)",
        "Matières avec coefficients configurables",
        "Relations enseignant ↔ matière ↔ classe"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.5
    story.append(Paragraph("5.5 Emploi du temps", styles['SubSection']))
    for item in [
        "Création et modification d’emplois du temps par classe",
        "Gestion des salles",
        "Détection simple des conflits (enseignant ou salle déjà pris)",
        "Vues par classe, par enseignant et par élève",
        "Export PDF et impression"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.6
    story.append(Paragraph("5.6 Notes et évaluations", styles['SubSection']))
    for item in [
        "Saisie des notes par enseignant (devoirs, contrôles, examens)",
        "Types d’évaluation configurables",
        "Calcul automatique des moyennes (par matière, par période, générale)",
        "Génération de bulletins au format PDF",
        "Validation optionnelle des notes par la direction",
        "Historique complet des notes"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.7
    story.append(Paragraph("5.7 Absences et retards", styles['SubSection']))
    for item in [
        "Saisie des absences et retards (enseignant ou secrétariat)",
        "Upload de justificatifs",
        "Notifications automatiques aux parents par email",
        "Statistiques d’assiduité",
        "Alertes automatiques en cas de seuil d’absences dépassé"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.8
    story.append(Paragraph("5.8 Frais de scolarité et paiements", styles['SubSection']))
    for item in [
        "Définition des frais (inscription, scolarité, transport, cantine…)",
        "Facturation par élève et par année scolaire",
        "Enregistrement des paiements (espèces, virement, chèque)",
        "Génération de reçus PDF",
        "Suivi des soldes et relances",
        "Tableau de bord financier"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.9
    story.append(Paragraph("5.9 Communication", styles['SubSection']))
    for item in [
        "Annonces générales ou ciblées (classe, niveau, parents)",
        "Messagerie interne simple (enseignant ↔ parent / élève)",
        "Notifications par email"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.10
    story.append(Paragraph("5.10 Tableaux de bord et reporting", styles['SubSection']))
    for item in [
        "Tableau de bord Direction (effectifs, absences, finances, résultats)",
        "Tableau de bord Enseignant (classes, notes à saisir)",
        "Tableau de bord Parent / Élève",
        "Exports Excel et PDF (listes, notes, absences, paiements)",
        "Statistiques graphiques"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # 5.11
    story.append(Paragraph("5.11 Administration système", styles['SubSection']))
    for item in [
        "Gestion des années scolaires (ouverture / clôture)",
        "Paramètres de l’établissement",
        "Documentation et procédures de sauvegarde du fichier SQLite",
        "Gestion des documents types (bulletins, certificats…)"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 6. EXIGENCES TECHNIQUES ==========
    story.append(Paragraph("6. Exigences techniques", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("Stack technique retenue", styles['SubSection']))

    stack_data = [
        ["Composant", "Technologie"],
        ["Framework backend", "Django 5.x"],
        ["Base de données", "SQLite"],
        ["Frontend", "Django Templates + HTMX + Alpine.js + Tailwind CSS"],
        ["Authentification", "Django Auth + Groupes"],
        ["Génération PDF", "WeasyPrint ou ReportLab"],
        ["Emails", "Django Email Backend"],
        ["Tâches asynchrones", "Celery + Redis (optionnel)"],
        ["Déploiement", "Docker ou Gunicorn + Nginx"],
    ]
    story.append(create_table(stack_data, [6*cm, 10*cm], styles))

    story.append(Paragraph("Configuration SQLite recommandée", styles['SubSection']))
    story.append(Paragraph(
        "Dans <b>settings.py</b> :",
        styles['NormalFR']
    ))
    story.append(Paragraph(
        "DATABASES = {<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;'default': {<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'ENGINE': 'django.db.backends.sqlite3',<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'NAME': BASE_DIR / 'db.sqlite3',<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;}<br/>"
        "}",
        styles['CodeStyle']
    ))

    story.append(Paragraph("Optimisations SQLite recommandées", styles['SubSection']))
    for item in [
        "Activer le mode WAL (Write-Ahead Logging) pour de meilleures performances en écriture concurrente",
        "PRAGMA journal_mode=WAL;",
        "PRAGMA synchronous=NORMAL;",
        "Effectuer des sauvegardes régulières du fichier db.sqlite3",
        "Éviter les très grosses transactions"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    story.append(Paragraph("Sécurité", styles['SubSection']))
    for item in [
        "HTTPS obligatoire en production",
        "Protection CSRF, XSS et SQL Injection (natives Django)",
        "Hachage sécurisé des mots de passe",
        "Rate limiting sur les tentatives de connexion",
        "Logs d’accès",
        "Conformité RGPD (droit à l’oubli, export des données, consentement)"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    story.append(Paragraph(
        "<b>Note importante :</b> SQLite est parfaitement adapté pour un établissement de 200 à 600 élèves. "
        "En cas de forte croissance ou de besoins de haute disponibilité, une migration vers PostgreSQL "
        "restera possible grâce à l’ORM Django.",
        styles['BodyTextFR']
    ))

    # ========== 7. ARCHITECTURE APPS ==========
    story.append(Paragraph("7. Architecture des apps Django recommandée", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph(
        "Organisation modulaire recommandée pour faciliter la maintenance et l’évolution :",
        styles['BodyTextFR']
    ))

    apps_structure = [
        ["App", "Responsabilité"],
        ["config/", "settings, urls, wsgi, asgi"],
        ["accounts/", "Utilisateurs, profils, rôles et permissions"],
        ["students/", "Élèves + relation avec les parents"],
        ["teachers/", "Enseignants et affectations"],
        ["academics/", "Années scolaires, niveaux, classes, matières"],
        ["timetable/", "Emploi du temps et salles"],
        ["grades/", "Notes, évaluations et bulletins"],
        ["attendance/", "Absences et retards"],
        ["finance/", "Frais de scolarité et paiements"],
        ["communication/", "Annonces et messagerie"],
        ["core/", "Utilitaires, tableaux de bord, exports"],
    ]
    story.append(create_table(apps_structure, [4*cm, 12*cm], styles))

    # ========== 8. MODÈLE DE DONNÉES ==========
    story.append(Paragraph("8. Modèle de données principal", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("Entités principales :", styles['NormalFR']))
    entites = [
        "User + Profile (extension du modèle utilisateur Django)",
        "AcademicYear (année scolaire)",
        "Level / ClassRoom (niveaux et classes)",
        "Subject (matières)",
        "Student (élèves)",
        "Teacher (enseignants)",
        "Parent + relation Parent-Student",
        "Enrollment (inscription élève ↔ classe ↔ année)",
        "Schedule / TimetableSlot (emploi du temps)",
        "Assessment / Grade (notes et évaluations)",
        "Absence (absences et retards)",
        "Fee / Invoice / Payment (frais et paiements)",
        "Announcement / Message (communication)",
        "Document (fichiers uploadés)"
    ]
    for e in entites:
        story.append(Paragraph(f"• {e}", styles['ListItemFR']))

    story.append(Paragraph("Principes de conception :", styles['SubSection']))
    for item in [
        "Soft delete (archivage) sur les données sensibles plutôt que suppression définitive",
        "Timestamps systématiques (created_at, updated_at)",
        "Clés étrangères avec on_delete appropriés (PROTECT, CASCADE, SET_NULL)",
        "Indexes sur les champs de recherche et de filtrage fréquents",
        "Contraintes d’unicité métier (matricule, etc.)"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 9. EXIGENCES NON FONCTIONNELLES ==========
    story.append(Paragraph("9. Exigences non fonctionnelles", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    for item in [
        "Temps de réponse des pages principales < 2 secondes",
        "Interface responsive (mobile + desktop)",
        "Accessibilité : niveau WCAG 2.1 AA souhaitable",
        "Code propre, respectant PEP8 et les conventions Django",
        "Tests unitaires et d’intégration (pytest-django recommandé)",
        "Documentation technique + documentation utilisateur",
        "Sauvegarde quotidienne du fichier SQLite",
        "Disponibilité cible : 99 % en production"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 10. PHASES ==========
    story.append(Paragraph("10. Phases de réalisation recommandées", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    story.append(Paragraph("Phase 1 – MVP (6 à 10 semaines)", styles['SubSection']))
    for item in [
        "Authentification + gestion des rôles",
        "Gestion des élèves, enseignants et classes",
        "Saisie des notes de base",
        "Gestion des absences",
        "Tableaux de bord simples"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    story.append(Paragraph("Phase 2 – Fonctionnalités avancées", styles['SubSection']))
    for item in [
        "Emploi du temps complet",
        "Génération de bulletins PDF",
        "Module finance (frais + paiements)",
        "Module de communication"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    story.append(Paragraph("Phase 3 – Finalisation et optimisation", styles['SubSection']))
    for item in [
        "Reporting avancé et graphiques",
        "Améliorations UX/UI",
        "Tests complets et corrections",
        "Documentation finale et déploiement"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 11. LIVRABLES ==========
    story.append(Paragraph("11. Livrables attendus", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    for item in [
        "Code source versionné (Git)",
        "Fichier db.sqlite3 de démonstration avec données de test",
        "Documentation technique (architecture, installation, modèles)",
        "Documentation utilisateur (guides par rôle)",
        "Scripts de sauvegarde et de restauration SQLite",
        "Guide de déploiement (Docker ou classique)",
        "Cahier de tests"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== 12. CONTRAINTES ==========
    story.append(Paragraph("12. Contraintes et hypothèses", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceBefore=0, spaceAfter=8))

    for item in [
        "Un seul établissement géré dans la version 1 (extensible ensuite)",
        "Les comptes utilisateurs sont créés exclusivement par l’administration",
        "L’année scolaire est gérée manuellement (ouverture / clôture)",
        "SQLite est adapté jusqu’à environ 400–600 élèves actifs",
        "Migration vers PostgreSQL possible ultérieurement grâce à l’ORM Django",
        "Les paiements en ligne (Stripe, etc.) sont hors scope de la v1"
    ]:
        story.append(Paragraph(f"• {item}", styles['ListItemFR']))

    # ========== CONCLUSION ==========
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=5, spaceAfter=10))
    story.append(Paragraph(
        "<b>Ce cahier des charges constitue la base de référence pour le développement de l’application "
        "de gestion scolaire avec Django et SQLite.</b> Il peut être utilisé comme document contractuel "
        "ou comme roadmap de développement. Toute évolution significative devra faire l’objet d’un avenant.",
        styles['BodyTextFR']
    ))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(
        "Document généré le 21 septembre 2026 – Version 1.1",
        styles['MetaInfo']
    ))

    # Build
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    print(f"PDF généré avec succès : {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
