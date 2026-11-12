# Détection du poste depuis l'offre et les emails

## Règles utilisées

La détection fonctionne localement, à partir du texte d'offre enregistré et des emails déjà liés à la candidature. Elle n'ouvre pas l'URL de l'offre et ne nécessite aucun service externe d'IA.

L'offre est prioritaire lorsqu'elle fournit un intitulé exploitable :

1. Libellé explicite sur une ligne : **Intitulé du poste**, **Poste**, **Titre**, **Fonction**, **Job title** ou **Position**, suivi de deux-points.
2. À défaut, titre isolé dans les premières lignes, avec un indice de métier ; la recherche s'arrête avant les sections de missions, profil ou compétences.
3. À défaut, formulation explicite comme **Nous recherchons une Consultante GRC pour…**.

Les retours à la ligne et les titres des offres collées en HTML sont conservés pour cette analyse ; aucun HTML n'est exécuté. Les sections d'offres similaires sont écartées. Des libellés explicites contradictoires, une compétence seule, une URL ou un simple nom d'entreprise ne sont pas des preuves suffisantes. En l'absence d'intitulé d'offre, les règles d'emails restent disponibles, notamment les titres cités dans les accusés de réception ou dans le sujet.

Les indices de métiers ont été élargis au-delà des postes techniques : analyste, consultant, auditeur, chargé de recrutement, juriste, gestionnaire, etc. Ces indices ne définissent pas la liste des formations du campus : le catalogue de promotions reste administrable et indépendant. Les règles restent heuristiques ; un titre absent ou ambigu peut ne pas être détecté.

## Fiches automatiques et corrections manuelles

Lors d'une réanalyse, l'intitulé fiable de l'offre peut enrichir une fiche **sans correction manuelle**, y compris une fiche sans email. Sans offre exploitable, un titre d'email n'est choisi que s'il améliore le score du titre courant ; une égalité ne remplace pas arbitrairement le titre. Le sujet peut servir même lorsque le corps n'est pas archivé ; le message reste compté parmi ceux sans contenu et son statut n'est pas reclassé à partir d'un corps absent.

Un import de nouveaux emails utilise aussi l'offre d'une fiche à laquelle le message a déjà été rattaché. Le rapprochement reste strict : ce changement ne fusionne pas deux postes différents chez une même entreprise et ne réaffecte pas les messages.

Les fiches corrigées manuellement conservent leurs détails. Sur la fiche, une suggestion différente du titre enregistré peut apparaître avec sa source (**offre** ou **emails liés**) :

1. Cliquer sur **Utiliser ce poste** pour remplir le champ Poste.
2. Relire la proposition et les autres champs.
3. Cliquer sur **Enregistrer les modifications** pour confirmer.

Le clic seul n'enregistre rien. Il reste possible de saisir un autre intitulé, plus court ou de score égal, ou de laisser volontairement le champ vide. Le choix explicite de l'utilisateur est désormais enregistré tel quel et n'est plus refusé par l'ancien score heuristique. Les protections des corrections manuelles restent actives lors des imports et réanalyses suivants.

Pour appliquer les nouvelles règles aux fiches automatiques déjà archivées, redémarrer Flask et le worker, puis utiliser **Réanalyser mes emails archivés**. L'enregistrement du texte de l'offre ne modifie pas le titre à lui seul.

## Vérification

```bash
.venv/bin/python -m unittest tests.test_job_titles tests.test_extractor tests.test_owned_reclassifier -v
node --test tests/application.test.cjs tests/login-sync.test.cjs
```

Les tests utilisent uniquement des bases temporaires et des messages fictifs. Ils couvrent plusieurs domaines de formation, les libellés et titres HTML, les cas ambigus, la priorité de l'offre, les sujets sans corps, l'isolation, les choix manuels de score égal ou inférieur, l'idempotence, la conservation des dates et le remplissage du champ sans enregistrement automatique. Aucune réanalyse réelle ni aucun scan personnel n'est lancé pendant ces contrôles.
