# miniai

CLI console de complétion de code assistée par IA.

## Utilisation

```bash
./bin/miniai "def add(a, b):"
# ou via stdin
echo "def add(a, b):" | ./bin/miniai
```

## Structure du dépôt

```
bin/miniai        point d'entrée bash
src/miniai/       logique Python (cli.py, ...)
tests/            tests
docs/             documentation
```

## Développement

Prérequis : Python 3.9+, bash.

```bash
python3 -m pip install -r requirements.txt  # une fois des dépendances ajoutées
python3 -m pytest
```

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE).
