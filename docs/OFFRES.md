# Conserver l'offre d'emploi d'une candidature

## Ajouter l'offre

Lors de la création d'une candidature manuelle, les champs **Lien de l'offre** et **Texte de l'offre** sont facultatifs. Copier-coller le contenu utile : poste, missions, compétences, contrat et conditions.

Pour une candidature existante, ouvrir sa fiche puis la section **L'offre associée**. Renseigner ou remplacer les champs, puis cliquer sur **Enregistrer l'offre**. Effacer un champ puis enregistrer permet de le vider. Le formulaire est distinct de celui des corrections de candidature : il ne change ni statut, ni poste, ni note, ni marqueur de correction manuelle, ni date du dernier email.

Le contenu enregistré apparaît sur la fiche, avec les retours à la ligne. Le bouton **Ouvrir l'offre d'origine** ouvre le lien dans un nouvel onglet. Le texte peut ainsi rester consultable même si le site retire l'annonce.

Le lien est seulement conservé. Aucun téléchargement, scraping ou appel réseau n'est lancé par l'enregistrement ou l'affichage. Le texte enregistré peut maintenant servir à [la détection du poste](DETECTION_POSTES.md), via les suggestions et la réanalyse. La seule sauvegarde du texte ne modifie pas le titre de la candidature.

## Limites et protections

- Texte : 100 000 caractères au maximum, après suppression des espaces extérieurs ; les retours à la ligne internes sont conservés.
- URL : 2 048 caractères au maximum, uniquement HTTP ou HTTPS, sans identifiants intégrés, espaces ou caractères de contrôle. Aucun lien `javascript:`, `data:` ou `file:` n'est accepté.
- Le texte reste du texte échappé : les balises collées ne sont pas exécutées. L'ouverture du lien utilise `noopener noreferrer`.
- Les formulaires conservent le CSRF ; le propriétaire vient de la session. Une autre personne, même authentifiée, ne peut ni lire ni modifier l'offre d'une candidature étrangère.
- Les erreurs de validation réaffichent le formulaire avec la saisie et ne remplacent pas l'offre existante. Les scans et réanalyses ne modifient pas les champs d'offre.
- La suppression de la candidature supprime également ses champs d'offre. La conservation des emails associés suit le comportement existant.

## Mise à jour et migration

Après sauvegarde de la base, redémarrer Flask et le worker depuis la branche contenant cette évolution. L'initialisation ajoute `applications.offer_text` et `applications.offer_url`, deux champs texte non nuls avec une valeur vide par défaut. Les candidatures existantes n'ont donc pas d'offre préremplie. Une seconde initialisation ne répète pas l'ajout et ne réécrit pas les données.

La saisie d'une offre ne nécessite pas le worker. Celui-ci reste nécessaire pour les scans et les réanalyses habituels. Cette évolution ne contacte pas les messageries et n'utilise pas les caches OAuth.

## Vérification

```bash
.venv/bin/python -m unittest tests.test_offers -v
```

Les tests utilisent uniquement des bases temporaires et des messages fictifs. Ils vérifient la migration, les limites, les protocoles URL, la création, la modification indépendante des statuts, l'isolation, le CSRF, l'échappement HTML, la conservation de la saisie en erreur et la préservation des offres pendant import et réanalyse.
