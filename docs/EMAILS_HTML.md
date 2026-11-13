# Affichage des emails HTML

La fiche d'une candidature affiche la mise en forme utile des emails : paragraphes, titres, listes, tableaux et liens. Un volet permet de consulter le texte archivé.

Les prochains scans conservent l'alternative HTML du corps du message, jusqu'à un million de caractères, séparément du texte utilisé par la détection et la réanalyse. Les pièces jointes HTML et les messages attachés sont exclus. Les checkpoints et la détection restent fondés sur le même pipeline.

Les anciennes archives contenant des balises HTML, éventuellement encodées, bénéficient également de cet affichage. Si seul le texte a été conservé, la mise en forme originale ne peut pas être reconstituée. Aucun téléchargement rétroactif ni scan réel n'est lancé par l'ouverture d'une fiche.

## Protection de l'affichage

Le HTML archivé est non fiable. Il est nettoyé à chaque affichage avec [nh3](https://nh3.readthedocs.io/en/latest/) selon une liste restrictive de balises et d'attributs, puis placé dans une iframe `srcdoc` dont la valeur est échappée par Jinja. Aucun HTML de message n'est injecté directement dans la page principale.

Les scripts, formulaires, objets, styles d'expéditeur et images (distantes ou intégrées) sont retirés. La politique CSP du document interdit les chargements réseau ; le sandbox n'autorise ni scripts, ni accès à l'origine de l'application, ni navigation de la page principale. Les liens HTTP/HTTPS absolus sont disponibles après clic, dans un nouvel onglet sans accès à la fenêtre d'origine et sans référent. Un lien autorisé peut toujours conduire vers un site trompeur : son contenu n'est pas vérifié par l'application.

Les droits restent ceux des candidatures : un apprenant consulte ses propres emails. L'équipe pédagogique ne reçoit aucun accès supplémentaire aux emails d'autrui. Lire une fiche ne modifie pas l'archive.

## Installation et vérification

Installer les dépendances avec `.venv/bin/python -m pip install -r requirements.txt`, puis redémarrer le serveur web et le worker. L'initialisation habituelle ajoute la colonne `emails.html_body` sans modifier les corps existants. La migration d'unicité conserve également ce champ.

Les tests utilisent des messages synthétiques et des bases temporaires : HTML hostile, liens, sandbox, isolement entre comptes, MIME et import/checkpoint. Ils ne remplacent pas une vérification visuelle dans le navigateur et ne déclenchent aucun scan personnel.
