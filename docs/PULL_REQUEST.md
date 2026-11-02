# Finaliser le pipeline personnel et préparer la démonstration Campus hors ligne

## Proposition de PR

Base : `main` · branche : `feature/demo-campus-finalisation`.

Le scan personnel existait côté worker mais restait inaccessible depuis Flask. Cette modification valide le pipeline IMAP → détection → import SQLite → checkpoint sans réseau, corrige les défauts reproduits et réactive uniquement `/scan` et `/jobs` avec le propriétaire issu de la session et le CSRF conservé.

Une démonstration isolée ajoute Alice et Bob, des candidatures et emails fictifs, un exemple d'import, de jobs et de checkpoints. Elle refuse l'écrasement d'un dossier existant, ignore la configuration de base habituelle et bloque les connexions sortantes. Les mots de passe fictifs sont demandés sans affichage ; aucun vrai jeton n'est utilisé.

## Points de revue

- Checkpoints enregistrés seulement après commit de l'import, avec comparaison de la configuration complète et du curseur précédent.
- UID illisible : synchronisation partielle, reprise et déduplication.
- Cache OAuth séparé par utilisateur/compte, parents symboliques refusés ; anciens caches conservés mais non automatiquement réutilisés.
- TLS direct ou STARTTLS obligatoire ; exceptions brutes retirées des logs.
- Anciens jobs sans propriétaire conservés et ignorés ; nouvelle réservation uniquement pour les jobs personnels actifs.
- Routes non migrées toujours bloquées : exports, connecteurs, réanalyse. Interface adaptée à leur indisponibilité.
- Tests auparavant non collectés rendus exécutables ; arrêt du worker corrigé ; debugger désactivé.
- Nouveau libellé Acceptée utilisable manuellement, sans modification des règles automatiques de classification.

## Validation locale

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
npx --yes pyright
.venv/bin/python -m unittest discover -s tests -v
```

Les résultats finaux sont consignés dans `docs/VALIDATION.md`. Les scénarios d'intégration emploient un transport fictif et de vraies transactions SQLite temporaires. Les tests de démo vérifient qu'une base sentinelle externe reste inchangée.

## Démonstration

```bash
.venv/bin/python demo.py init
.venv/bin/python demo.py serve
```

Puis http://127.0.0.1:5001 ; scénario détaillé dans `docs/DEMO.md`.

## Limites de cette PR

Pas de synchronisation fournisseur réelle, pas de migration des données/jetons existants, pas de déploiement. Linux/Unix requis pour `fcntl`. Le serveur de développement reste local. Les anciens caches OAuth nécessitent une migration contrôlée ou une nouvelle autorisation ; le changement de chemin ne les supprime pas.

Aucun push ni aucune PR distante ne sont effectués par la préparation de cette proposition.
