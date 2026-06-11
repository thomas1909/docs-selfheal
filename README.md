# Docs Selfheal — documentation auto-réparante

> **Projet 4 du guide BASWE.** Une GitHub Action qui détecte, à chaque PR, les
> sections de documentation rendues obsolètes par les changements de code, et
> propose soit un correctif automatique, soit un flag pour revue humaine — selon
> un score de confiance.

## Le problème

La doc de toutes les équipes est en retard sur le code. Personne ne pense à mettre
à jour `docs/guide.md` quand il renomme un paramètre. Ce projet vit **dans la CI**,
pas dans une démo Streamlit.

## Pipeline

```
code (ast) ──> chunks sémantiques (signature, docstring, body-hash)
docs (md)  ──> sections par heading (+ refs de code extraites des backticks)
                        │
                 graphe code <-> docs  (name-match puis similarité lexicale)
                        │
git diff (2 snapshots) ─> changements significatifs (ast-based : le bruit de
                          formatage/commentaires est invisible par construction)
                        │
                 sections suspectes ─> vérif de staleness (déterministe + hook LLM)
                        │
            corrections ciblées ── confiance ≥ 0.85 ──> auto-fix (PR)
                        └────────── sinon ──> TODO(docheal) + revue humaine
```

- **Parseur de code** (`code_parser.py`) : ast pur — fonctions, classes, méthodes,
  signatures complètes (annotations + défauts), docstrings, hash du corps.
  Identifiant stable `fichier::qualname`.
- **Parseur de docs** (`doc_parser.py`) : sections markdown par chemin de heading
  (`Guide > Configuration`), références de code extraites des backticks.
- **Graphe de liens** (`linker.py`) : name-match exact d'abord, similarité
  lexicale en repli (interface prête pour de vrais embeddings).
- **Diff significatif** (`diffing.py`) : comparé sur signature + hash ast, donc
  les changements de commentaires/espaces ne déclenchent jamais rien. Priorité :
  suppressions > signatures > ajouts > corps.
- **Réparation** (`repair.py`) : si l'ancienne signature est citée textuellement
  dans la doc → remplacement mécanique **auto-fix** validé par un quality gate
  (la nouvelle signature doit apparaître, l'ancienne disparaître, la section ne
  doit pas rétrécir de moitié). Sinon → brouillon avec `TODO(docheal)` et revue.

## Démarrage

```bash
uv sync --extra dev --link-mode=copy
uv run --no-sync pytest -v        # 8 tests offline

# Comparer deux snapshots du code contre la doc
uv run --no-sync docheal check --old ./snapshot_main --new . --docs docs
# → résumé markdown façon commentaire de PR + exit code 1 si doc obsolète
```

## En tant que GitHub Action

`action.yml` (action composite) : snapshot de la base via `git worktree`, exécution
de `docheal check`, commentaire de PR avec le résumé :

```
## Doc Check Results
- ✅ 3 section(s) vérifiée(s) exacte(s)
- 🔧 1 correction(s) automatique(s) proposée(s)
- 👀 2 section(s) à revoir manuellement
```

## Mesurer la précision

Sur un repo de test : compter vrais/faux positifs (sections exactes flaguées),
faux négatifs (staleness ratée) et qualité des corrections. La conception ast-based
élimine la classe de faux positifs la plus courante (churn de formatage).
