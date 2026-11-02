# Backoffice de création des comptes

## Créer le premier administrateur

Cette étape se fait depuis le terminal de la machine qui héberge la base. Aucun compte existant n'est automatiquement promu et aucun administrateur n'est ajouté à la base réelle pendant les tests.

```bash
.venv/bin/python create_account.py admin@campus.invalid --role admin
```

L'adresse ci-dessus est un exemple d'identifiant local, à remplacer si besoin. Choisir une adresse qui n'est pas déjà utilisée. Saisir puis confirmer le mot de passe sans affichage : 12 à 256 caractères. Le script et le backoffice utilisent les mêmes règles de validation et le hachage scrypt.

## Ouvrir le backoffice

Redémarrer Flask pour charger les nouvelles routes :

```bash
.venv/bin/python web.py
```

Se connecter avec le compte administrateur. Le lien **Administration** apparaît dans la navigation et **Gérer les comptes utilisateurs** dans la page Mon compte. URL directe : **http://127.0.0.1:5000/admin/users**.

Aucun worker n'est nécessaire pour la création des comptes. Les opérations administratives sont locales à SQLite et ne contactent aucun fournisseur de messagerie.

## Créer un compte depuis l'interface

1. Ouvrir **Administration**, puis **Créer un compte**.
2. Renseigner l'adresse de connexion et choisir le rôle : **Apprenant** (par défaut), **Formateur** ou **Administrateur**.
3. Saisir le mot de passe initial et sa confirmation, puis enregistrer.
4. Le compte actif apparaît dans la liste et peut se connecter immédiatement. Aucun mot de passe ou hash n'est affiché dans cette liste ni dans le message de confirmation.

Une adresse déjà utilisée est refusée sans modifier le compte existant. Les erreurs du formulaire conservent l'adresse et le rôle, mais les deux champs de mot de passe restent vides.

Le mot de passe initial doit être transmis directement au destinataire par un moyen adapté. Cette version ne fournit pas d'envoi d'invitation, de lien de récupération ni de changement imposé à la première connexion. Elle ne permet pas non plus de modifier le rôle ou le mot de passe d'un compte existant dans ce backoffice.

## Désactiver ou réactiver

La liste affiche l'adresse, le rôle, l'état et la date de création en UTC. Le bouton **Désactiver** bloque les connexions et invalide l'accès d'une session déjà ouverte à sa requête suivante. **Réactiver** redonne l'accès avec le mot de passe existant.

La désactivation ne supprime ni le compte, ni les candidatures, ni les emails, ni les connecteurs. Elle ne constitue pas une annulation immédiate des opérations déjà engagées. Les nouveaux jobs d'un compte inactif ne sont pas réservés par le worker personnel.

Un administrateur ne peut pas se désactiver lui-même depuis cette interface. L'autorisation de l'administrateur acteur est revérifiée dans la transaction d'écriture : un administrateur désactivé ne peut pas à son tour désactiver celui qui reste actif. Les changements d'état explicites sont idempotents : un double envoi ne réactive pas accidentellement un compte.

## Périmètre de sécurité

- Les routes `/admin/users`, `/admin/users/new` et les POST de création/activation sont réservées aux administrateurs authentifiés et actifs. Les autres rôles reçoivent 403, même avec une URL ou un formulaire forgé.
- Masquer le lien de navigation n'est pas le contrôle de sécurité : le blueprint et les services SQLite vérifient les droits.
- Le rôle et l'activation de l'acteur sont revérifiés dans la transaction, y compris après le calcul du hash lors d'une création.
- Tous les POST conservent la protection CSRF. Les mots de passe ne sont jamais placés dans les URL, messages flash ou valeurs de formulaire retournées.
- La liste sélectionne uniquement les métadonnées des comptes, sans lire leurs hashes.
- Le rôle administrateur autorise la gestion des identités, pas la lecture transversale des candidatures ou des messageries. Les modules personnels conservent leurs contrôles `user_id`.
- Le serveur de développement reste sur 127.0.0.1, avec le debugger désactivé. Une exposition réseau nécessite un déploiement approprié avec HTTPS ; le serveur local n'est pas présenté comme un hébergement de production.

## Validation

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
npx --yes pyright
.venv/bin/python -m unittest discover -s tests -v
```

Les tests du backoffice utilisent uniquement une base temporaire et des mots de passe fictifs. Ils couvrent les rôles, la création, les doublons, les erreurs de saisie, les mots de passe hachés et non réaffichés, le CSRF, les droits revérifiés après calcul du hash, la révocation des sessions et la conservation des candidatures. Aucune création ou désactivation n'est exécutée sur la base réelle par cette validation.

Dernier contrôle local : **202 tests réussis**, dont 21 tests du backoffice ; Ruff conforme et Pyright sans erreur ni avertissement.
