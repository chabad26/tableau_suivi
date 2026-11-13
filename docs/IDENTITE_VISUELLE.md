# Couleurs du Campus

Le thème conserve les fonds sombres de Job Tracker et reprend les couleurs publiées sur le [site du Campus Numérique](https://le-campus-numerique.fr/), dans sa [palette Elementor](https://le-campus-numerique.fr/wp-content/uploads/elementor/css/post-7.css), consultée le 13 novembre 2026 : rose `#EF2961`, bleu `#2F82C5`, orange `#F76534`.

Le bandeau commun identifie le Campus et Job Tracker, avec ces trois couleurs. Les actions principales utilisent un rose foncé `#C91B50` et un texte blanc ; les liens et accents utilisent un rose clair `#FF86AA` adapté au fond sombre. Les badges et les messages conservent des couleurs distinctes pour leurs statuts. Aucune police, image ni feuille de style distante n'est chargée par le thème.

Les variables sont centralisées en tête de `static/style.css`. Les liens, y compris après visite, suivent la couleur commune ; les boutons conservent leur propre couleur de texte. Le focus clavier est visible sur les liens, boutons, champs et volets. La feuille de style est versionnée dans `templates/base.html` pour renouveler son cache après cette mise à jour.

## Vérifications

Les principaux couples texte/fond ajoutés ont un contraste calculé supérieur à 4,5:1 : bouton blanc sur rose 5,59:1, accent rose sur panneau 7,59:1, texte secondaire sur panneau adouci 7,11:1. Cela ne constitue pas un audit d'accessibilité complet.

Les captures Firefox de pages rendues avec une base temporaire ont été examinées : connexion à 1 440 px et candidatures à 390 px. Les 34 tests existants web, dashboard et synchronisation de connexion passent, ainsi que Ruff, le contrôle de format et `git diff --check`. Aucun compte, document ou email personnel n'est modifié.

## Signature Olidev

Le footer commun affiche « Offert par Olidev » avec la version à écriture blanche du logo fourni par le propriétaire, copiée dans `static/logo-olidev.jpg`. Le lien vers `https://www.olidev.ovh` s'ouvre dans un nouvel onglet sans accès à la fenêtre d'origine et sans référent. Le footer suit le contenu et reste en bas des pages courtes. Son rendu a été examiné dans Firefox à 1 440 et 390 px ; le rendu Flask et la réponse HTTP du fichier statique ont été vérifiés sur une base temporaire.
