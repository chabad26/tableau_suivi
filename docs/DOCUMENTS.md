# CV, lettres de motivation et échanges pédagogiques

## Accès et fonctionnement

L'onglet **CV et lettres** est disponible pour les deux profils du campus :

- **Apprenant** : ses seuls documents ; dépôt, nouvelles versions, téléchargement, échanges et suppression du document complet.
- **Équipe pédagogique (`admin`)** : choix d'un apprenant, consultation de ses documents et versions, téléchargement, messages et annotations. L'équipe ne remplace ni ne supprime les fichiers de l'apprenant.

L'équipe pédagogique peut consulter les documents conservés d'un apprenant désactivé. Le compte désactivé lui-même perd ses accès habituels. Les autorisations sont vérifiées dans les services et dans les transactions d'écriture, à partir du rôle et de l'activation en base. Le rôle historique `trainer` n'ouvre pas cet espace.

Ce lot autorise explicitement la consultation des CV/LM et de leurs échanges par l'équipe pédagogique. Il ne donne pas accès aux candidatures détaillées, offres, emails ou connecteurs des autres utilisateurs. Les annotations et messages sont internes à l'application ; aucun email ni notification externe n'est envoyé.

## Parcours apprenant

1. Ouvrir **CV et lettres**.
2. Choisir **CV** ou **Lettre de motivation**, renseigner un titre distinctif et sélectionner un PDF ou DOCX de **10 Mo maximum**.
3. Cliquer sur **Déposer le document**. Plusieurs documents du même type peuvent coexister, par exemple un CV Data, un CV GRC et une lettre pour une entreprise précise.
4. Sur la fiche, télécharger le fichier et échanger avec l'équipe. Un **message** constitue un échange général ; une **annotation** est un retour textuel avec un numéro de page facultatif. Il ne s'agit pas de dessiner ou de modifier directement le PDF/DOCX.
5. Utiliser **Déposer une nouvelle version** pour réviser ce document. Les versions précédentes restent disponibles dans le sélecteur ; chaque version conserve ses propres échanges.

Le titre est limité à 120 caractères, un message ou une annotation à 4 000 caractères. Le numéro de page d'une annotation, facultatif, est compris entre 1 et 9 999. Le numéro indique une référence fournie par l'auteur ; l'application ne calcule pas la pagination du fichier. Les retours à la ligne des échanges sont conservés et le HTML est échappé.

La suppression demande confirmation et supprime **tout le document**, ses versions et les échanges associés. Elle est réservée à son propriétaire. Les messages déjà enregistrés ne sont pas éditables séparément dans ce lot.

## Parcours pédagogique

Ouvrir **CV et lettres**, choisir d’abord la **promotion**, puis **Afficher les apprenants**. Choisir ensuite l’apprenant de cette promotion et cliquer sur **Consulter ses documents**. Changer de promotion retire la sélection précédente. L’option **Sans promotion renseignée** conserve l’accès aux comptes non affectés ; une promotion vide affiche un message explicite. Un lien existant vers un apprenant retrouve automatiquement sa promotion. La liste indique le nombre de documents, l'identifiant de connexion et la promotion. Ouvrir le document, choisir la version à relire, télécharger puis ajouter un message ou une annotation. L'auteur, son profil et l'heure UTC sont indiqués dans la discussion ; le profil d'auteur enregistré vient du serveur, jamais d'un champ de formulaire.

Un retour déposé sur une ancienne version reste sur cette ancienne version. Le lecteur choisit explicitement sa version pour ne pas attribuer un ancien commentaire à un nouveau fichier. Les nouveaux échanges deviennent visibles lors de l'ouverture ou du rechargement de la fiche ; il n'y a pas de messagerie temps réel dans ce lot.

## Stockage et protections

- Les fichiers sont privés : `DATABASE_PATH.parent/documents/<identifiant_apprenant>/<uuid>.pdf` ou `.docx`. Ils ne sont pas placés dans `static/` et ne sont pas publiés sous une URL de fichier direct.
- Les noms physiques sont générés par le serveur. Le nom de téléchargement est nettoyé ; les titres restent indépendants du nom du fichier.
- Les répertoires ont les permissions 0700 et les fichiers 0600. Les chemins symboliques, fichiers non réguliers et chemins physiques inattendus sont refusés.
- Chaque téléchargement vérifie les droits, la taille et l'empreinte SHA-256. Il est servi en pièce jointe, avec `nosniff`, absence de cache et une politique CSP restrictive. L'application ne rend pas le document dans une page HTML.
- Le type annoncé par le navigateur ne suffit pas : extension et signature PDF, ou structure ZIP/DOCX, sont contrôlées. Les archives avec macros connues, doublons d'entrées, chemins suspects, compression non prise en charge ou volume décompressé excessif sont refusées. Les contrôles ne constituent ni un antivirus ni une validation complète de la norme PDF/DOCX.
- Les limites de taille de requête sont relevées uniquement pour les deux routes de dépôt : 10 Mo de fichier plus une marge de formulaire. Les autres formulaires conservent leur limite de 2 Mo. Tous les POST restent protégés par CSRF.
- Un échec de création de version annule les métadonnées et retire le fichier nouvellement créé. Les droits sont revérifiés après validation du fichier. Une suppression utilise une mise à l'écart temporaire des fichiers pour les restaurer si la transaction échoue.

Les tests n'utilisent que des documents synthétiques et des répertoires temporaires. Aucun CV réel n'est ouvert, déposé ou supprimé pendant le développement.

## Mise à jour, sauvegarde et restauration

Redémarrer **Flask** pour initialiser les tables `documents`, `document_versions` et `document_comments` et charger les nouvelles routes. L'initialisation est additive et idempotente ; aucun répertoire ou document utilisateur n'est créé tant qu'aucun dépôt n'a lieu. Le worker n'est pas requis pour gérer les fichiers ou discuter ; les fonctions de messagerie habituelles continuent à utiliser leur worker.

Sauvegarder **la base SQLite et le dossier privé `documents/` ensemble**, en empêchant les dépôts et suppressions pendant la copie. Protéger les sauvegardes comme les fichiers d'origine. Restaurer seulement la base ou seulement les fichiers peut rendre des versions indisponibles. Le dossier par défaut est exclu du dépôt Git ; avec un emplacement SQLite personnalisé, conserver également les fichiers hors du dépôt et du répertoire public du serveur.

En cas d'arrêt brutal pendant une suppression, un fichier `.deleting-<nom_physique>` peut subsister. Mettre l'application en maintenance et vérifier les métadonnées avant intervention : si la version existe encore, restaurer son nom physique d'origine ; si la suppression est validée en base, purger le fichier mis à l'écart. Ne jamais restaurer automatiquement sous un autre propriétaire. Cette opération et les sauvegardes cohérentes seront reprises dans le guide de déploiement complet.

Le proxy et le serveur de production devront accepter les requêtes multipart nécessaires aux dépôts. L'espace disque doit être dimensionné pour les versions conservées ; ce lot ne définit pas de quota cumulé par apprenant.

## Vérification

```bash
.venv/bin/python -m unittest tests.test_documents -v
```

Les tests couvrent les deux formats, les versions et échanges séparés, les auteurs dérivés de la session, les profils, le CSRF, les accès interdits entre apprenants, les limites multipart, les fichiers invalides, les permissions, les symlinks, les modifications de fichiers, les identifiants invalides, les écritures échouées et la restauration après suppression annulée.
