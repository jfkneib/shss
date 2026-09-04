"""Base de "cas curates" : des demandes que le petit LLM ne sait
structurellement pas traiter (ex : "l'energie consommee par le pc" --
il n'invente rien de fiable la-dessus), pour lesquelles on ecrit le
script une fois a la main et on le retrouve ensuite par similarite de
sens plutot que de repasser par une generation a chaque fois.

Deux fichiers, deliberement separes :
  - le store curate (SHSS_CASES_PATH, defaut ~/.shss/cases.json) :
    edite a la main, relu comme du code (voir bin/shss-cases) --
    demande(s) exemple + script, jamais de vecteurs dedans.
  - le cache d'embeddings (a cote, cases.embeddings.json) : genere par
    machine, jamais edite a la main, reconstruit par
    `shss-cases reindex` quand le store change (is_stale()).

Branche dans llm.generate_bash(), juste apres les commandes internes
(voir commands.py) et avant tout appel au LLM de generation : une
demande qui matche un cas avec assez de confiance (best_match())
reutilise le script curate tel quel, sans jamais charger le modele de
generation. Si la base est vide (cas le plus courant, rien de curate
pour l'instant), best_match() ne charge meme pas le modele
d'embeddings -- aucun cout ajoute pour une demande ordinaire.

Cas "gabarit" (input="stdin") : le texte entre guillemets dans la
demande varie a chaque fois (ex: "corrige moi ma ligne bash : '...'")
-- extract_payload() l'isole avant le calcul de similarite (matching
sur la formulation autour, pas sur le contenu variable) et le
transmet au script sur son entree standard au moment de l'execution,
jamais colle dans le code du script -- aucun risque d'injection.
"""

import hashlib
import json
import math
import os
import re
import time
import urllib.request
from pathlib import Path

from .llm import (
    MODELS_DIR,
    SYSTEM_MODELS_DIR,
    _discover_ollama_only,
    _env_int,
    _gpu_layers,
)

# Modele dedie aux embeddings, distinct du modele de generation
# (MODEL_NAME/MODEL_TAG dans llm.py). Necessaire : un modele de
# generation generaliste (qwen2.5-coder) n'a jamais ete entraine pour
# que sa similarite cosinus separe "proche" de "pas proche" -- teste en
# pratique, une demande sans rapport avec aucun cas ressortait quand
# meme a >90% de similarite.
#
# Un seul modele propose, pas un choix (contrairement a CURATED_MODELS
# cote generation) : nomic-embed-text est celui qu'on a valide (voir
# discussion miniRAG), inutile d'ouvrir un menu pour un seul choix.
EMBED_MODEL_NAME = os.environ.get("SHSS_EMBED_MODEL_NAME", "nomic-embed-text")
EMBED_MODEL_TAG = os.environ.get("SHSS_EMBED_MODEL_TAG", "v1.5")

# Repli telechargeable directement (sans Ollama), meme mecanisme et
# memes dossiers partages que les modeles de generation curates
# (SYSTEM_MODELS_DIR / MODELS_DIR, voir llm.py). Q4_K_M plutot que le
# f16 que sert Ollama (~274 Mo) : un modele d'embeddings encaisse bien
# mieux la quantization qu'un modele generatif, et a cette taille (~80
# Mo) reste coherent avec le positionnement "leger" de shss. URL
# verifiee manuellement (HEAD request) avant d'etre codee en dur, meme
# convention que CURATED_MODELS.
CURATED_EMBED_MODEL_FILENAME = "nomic-embed-text-v1.5.gguf"
CURATED_EMBED_MODEL_URL = (
    "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/"
    "resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf"
)
CURATED_EMBED_MODEL_SIZE_MB = 81


def curated_embed_model_path() -> str:
    """Ou le modele d'embeddings curate est (ou serait) sur disque :
    l'emplacement partage s'il y est deja, sinon celui par utilisateur
    -- meme logique que llm.curated_model_path()."""
    system_path = SYSTEM_MODELS_DIR / CURATED_EMBED_MODEL_FILENAME
    if system_path.is_file():
        return str(system_path)
    return str(MODELS_DIR / CURATED_EMBED_MODEL_FILENAME)


def download_embedding_model() -> str:
    """Telecharge le modele d'embeddings curate (aucun effet si deja
    present, system ou par utilisateur) et retourne son chemin.
    Bloquant -- jamais appele automatiquement, seulement depuis un
    `shss-cases download-model` explicite (meme principe que
    llm.download_curated_model() : le telechargement reste une action
    demandee, pas une surprise au premier lancement)."""
    existing = Path(curated_embed_model_path())
    if existing.is_file():
        return str(existing)

    shared = hasattr(os, "geteuid") and os.geteuid() == 0
    dest_dir = SYSTEM_MODELS_DIR if shared else MODELS_DIR
    dest = dest_dir / CURATED_EMBED_MODEL_FILENAME

    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_name(dest.name + ".part")
    urllib.request.urlretrieve(CURATED_EMBED_MODEL_URL, tmp_dest)
    tmp_dest.rename(dest)
    if shared:
        dest_dir.chmod(0o755)
        dest.chmod(0o644)  # lisible par tous les utilisateurs de la machine
    return str(dest)


def discover_embedding_model_path(model=EMBED_MODEL_NAME, tag=EMBED_MODEL_TAG):
    """Comme llm.discover_gguf_path(), mais pour le modele d'embeddings :
    volontairement pas la meme fonction, ni le meme override
    (SHSS_EMBED_MODEL_PATH, pas SHSS_MODEL_PATH) -- sinon pointer
    SHSS_MODEL_PATH vers un modele de generation personnalise ferait
    aussi, par erreur, devier le modele d'embeddings."""
    override = os.environ.get("SHSS_EMBED_MODEL_PATH")
    if override:
        return override
    try:
        return _discover_ollama_only(model, tag)
    except FileNotFoundError:
        pass

    curated = curated_embed_model_path()
    if Path(curated).is_file():
        return curated

    raise FileNotFoundError(
        f"GGUF introuvable pour le modele d'embeddings ({model}:{tag} via "
        "Ollama, rien de telecharge non plus). "
        f"`shss-cases download-model` (~{CURATED_EMBED_MODEL_SIZE_MB} Mo), "
        f"`ollama pull {model}:{tag}`, ou SHSS_EMBED_MODEL_PATH vers un "
        ".gguf existant."
    ) from None


_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _cases_path() -> Path:
    override = os.environ.get("SHSS_CASES_PATH")
    if override:
        return Path(override)

    # SHSS_CASES_PROFILE : plusieurs bases separees (ex: "systeme",
    # "dev") plutot qu'une seule -- reduit le risque de faux positif
    # entre cas sans rapport (constate en pratique avec fix-select) et
    # permet de charger un profil different selon le contexte de
    # travail, sans avoir a synchroniser deux variables a la main
    # (SHSS_CASES_CACHE_PATH se deduit automatiquement de celle-ci,
    # voir _cache_path()).
    profile = os.environ.get("SHSS_CASES_PROFILE")
    if profile:
        if not _PROFILE_NAME_RE.match(profile):
            raise ValueError(
                f"SHSS_CASES_PROFILE invalide : {profile!r} "
                "(lettres, chiffres, - et _ seulement)"
            )
        return Path.home() / ".shss" / "profiles" / profile / "cases.json"

    return Path.home() / ".shss" / "cases.json"


def profile_dir(cases_path: Path = None) -> Path:
    """Repertoire du profil courant (~/.shss/profiles/<nom>/, ou
    ~/.shss/ pour le profil par defaut) -- expose aux cas curatés via
    SHSS_PROFILE_DIR (voir llm.py) pour qu'un cas puisse appeler un
    script range dans ce meme repertoire (sous scripts/, par
    convention) sans jamais coder un chemin en dur : contrairement a
    un chemin vers l'emplacement d'un clone git, ce repertoire est
    garanti present partout ou le profil a ete installe, quelle que
    soit la machine (voir profiles/pc-stats/README.md pour le
    cas concret qui a motive ceci -- deux cas y avaient ete ajoutes
    avec un chemin code en dur vers ce depot, cassant des que lance
    d'ailleurs)."""
    return (cases_path or _cases_path()).parent


def list_profiles():
    """Liste triee des profils connus (sous-dossiers de
    ~/.shss/profiles/ contenant un cases.json) -- le profil par defaut
    (base racine, sans SHSS_CASES_PROFILE) n'y figure pas, c'est
    toujours une option implicite en plus de cette liste."""
    base = Path.home() / ".shss" / "profiles"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "cases.json").is_file())


def _cache_path(cases_path: Path = None) -> Path:
    override = os.environ.get("SHSS_CASES_CACHE_PATH")
    if override:
        return Path(override)
    cases_path = cases_path or _cases_path()
    return cases_path.with_name(cases_path.stem + ".embeddings.json")


def load_cases(path=None):
    """Retourne la liste des cas curates, ou [] si le store n'existe
    pas encore (rien de curate pour l'instant -- pas une erreur)."""
    path = path or _cases_path()
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_cases(cases, path=None):
    path = path or _cases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _find_case(cases, case_id):
    for case in cases:
        if case["id"] == case_id:
            return case
    return None


def add_case(cases, case_id, requests, script, note="", input_mode=None, threshold=None):
    """Retourne une nouvelle liste avec `case_id` ajoute. Leve
    ValueError si l'id existe deja -- on modifie/retire explicitement
    un cas curate, on ne l'ecrase jamais silencieusement.

    `input_mode="stdin"` (stocke dans le cas sous la cle "input") : le
    contenu entre guillemets de la demande (voir extract_payload()) est
    transmis au script sur son entree standard au lieu d'etre ignore --
    un cas "gabarit", pour une demande dont le contenu varie a chaque
    fois autour d'une formulation stable.

    `threshold` : seuil de confiance propre a ce cas, prioritaire sur
    DEFAULT_THRESHOLD/SHSS_CASES_THRESHOLD. Un cas gabarit a souvent
    besoin d'un seuil plus eleve que la moyenne : une fois le contenu
    entre guillemets normalise (voir extract_payload), il ne reste
    souvent que le gabarit de phrase ("corrige ... : \"...\"") pour
    distinguer un cas d'un autre -- constate en pratique, plusieurs
    demandes sans rapport (traduire, compter des mots...) peuvent
    quand meme depasser un seuil generique."""
    if _find_case(cases, case_id) is not None:
        raise ValueError(f"un cas « {case_id} » existe deja")
    if not requests:
        raise ValueError("il faut au moins une formulation d'exemple (--request)")
    if input_mode not in (None, "stdin"):
        raise ValueError(f"input invalide : {input_mode!r} (seul 'stdin' est reconnu)")
    case = {"id": case_id, "requests": list(requests), "script": script}
    if note:
        case["note"] = note
    if input_mode:
        case["input"] = input_mode
    if threshold is not None:
        case["threshold"] = float(threshold)
    return cases + [case]


def remove_case(cases, case_id):
    """Retourne une nouvelle liste sans `case_id`. Leve KeyError si
    absent."""
    if _find_case(cases, case_id) is None:
        raise KeyError(case_id)
    return [c for c in cases if c["id"] != case_id]


def update_case(cases, case_id, requests=None, script=None, note=None, input_mode=None, threshold=None):
    """Retourne une nouvelle liste avec `case_id` mis a jour en place
    (position preservee dans la liste) -- seuls les champs fournis
    (non None) sont remplaces, les autres restent tels quels. Leve
    KeyError si `case_id` n'existe pas (utiliser add_case() pour en
    creer un nouveau).

    `input_mode` : passer "stdin" ou "" (chaine vide, pour repasser un
    cas gabarit en cas normal -- None laisse le champ "input" tel quel,
    comme les autres champs).

    `threshold` : un float pour fixer le seuil propre a ce cas, "" pour
    le retirer (retour au seuil global), None pour laisser tel quel."""
    if _find_case(cases, case_id) is None:
        raise KeyError(case_id)
    if input_mode not in (None, "", "stdin"):
        raise ValueError(f"input invalide : {input_mode!r} (seul 'stdin' est reconnu)")

    def _updated(case):
        if case["id"] != case_id:
            return case
        new_case = dict(case)
        if requests is not None:
            new_case["requests"] = list(requests)
        if script is not None:
            new_case["script"] = script
        if note is not None:
            new_case["note"] = note
        if input_mode is not None:
            if input_mode:
                new_case["input"] = input_mode
            else:
                new_case.pop("input", None)
        if threshold is not None:
            if threshold == "":
                new_case.pop("threshold", None)
            else:
                new_case["threshold"] = float(threshold)
        return new_case

    return [_updated(c) for c in cases]


def _request_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Premiere chaine entre guillemets (simples ou doubles) dans une
# demande -- volontairement la premiere seulement : une demande n'a
# normalement qu'un seul contenu variable ("corrige moi ma ligne : '...'"),
# et prendre la premiere reste previsible si jamais il y en a plusieurs.
_QUOTED_RE = re.compile(r'"([^"]*)"|\'([^\']*)\'')


def extract_payload(text: str):
    """Retourne (payload, texte_normalise). `payload` est le contenu de
    la premiere chaine entre guillemets dans `text`, ou None s'il n'y
    en a pas. `texte_normalise` est `text` avec cette chaine remplacee
    par un marqueur fixe ('"..."') -- deux demandes qui ne different
    que par leur contenu entre guillemets ont ainsi le meme texte
    normalise, donc la meme similarite avec un cas curate, quel que
    soit ce contenu."""
    m = _QUOTED_RE.search(text)
    if not m:
        return None, text
    payload = m.group(1) if m.group(1) is not None else m.group(2)
    normalized = text[: m.start()] + '"..."' + text[m.end() :]
    return payload, normalized


class Embedder:
    """Charge paresseusement le modele GGUF actif en mode embedding.

    Un chargement llama.cpp separe de celui de llm.MiniLLM (generation) :
    modele different (voir EMBED_MODEL_NAME) et llama.cpp exige de
    toute facon `embedding=True` des le chargement, donc les deux modes
    ne pourraient pas partager une instance meme avec le meme modele.
    """

    def __init__(self, model_path=None):
        self.model_path = model_path or discover_embedding_model_path()
        self._llm = None

    def _ensure_loaded(self):
        if self._llm is None:
            from llama_cpp import Llama

            self._llm = Llama(
                model_path=self.model_path,
                embedding=True,
                n_threads=_env_int("SHSS_N_THREADS", None),
                n_gpu_layers=_gpu_layers(),
                verbose=False,
            )

    def embed(self, text: str):
        self._ensure_loaded()
        result = self._llm.create_embedding(text)
        vectors = result["data"][0]["embedding"]
        if vectors and isinstance(vectors[0], list):
            # Ce modele (pas specialise embeddings) n'a pas de pooling
            # cote llama.cpp : on recoit un vecteur par token, qu'on
            # moyenne en un seul vecteur de phrase.
            n = len(vectors)
            dim = len(vectors[0])
            return [sum(v[i] for v in vectors) / n for i in range(dim)]
        return vectors


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def reindex(cases, embedder=None, cache_path=None, force=False):
    """(Re)construit le cache d'embeddings pour `cases`, en reutilisant
    tout vecteur deja en cache pour une formulation dont le texte n'a
    pas change (ignore le cache existant si `force`). Ecrit le
    resultat dans `cache_path` et le retourne.

    `embedder` est injectable : les tests n'ont jamais besoin d'un
    vrai modele charge."""
    embedder = embedder or Embedder()
    cache_path = cache_path or _cache_path()

    old_entries = {}
    if not force and cache_path.is_file():
        try:
            old = json.loads(cache_path.read_text(encoding="utf-8"))
            for entry in old.get("entries", []):
                old_entries[(entry["case_id"], entry["hash"])] = entry["vector"]
        except (OSError, json.JSONDecodeError, KeyError):
            old_entries = {}

    entries = []
    for case in cases:
        for request in case["requests"]:
            h = _request_hash(request)
            vector = old_entries.get((case["id"], h))
            if vector is None:
                # Normalise avant d'embedder (voir extract_payload) : un
                # exemple colle avec son contenu reel entre guillemets
                # matche quand meme une demande future au contenu
                # different mais a la meme formulation autour.
                _payload, normalized = extract_payload(request)
                vector = embedder.embed(normalized)
            entries.append(
                {
                    "case_id": case["id"],
                    "request": request,
                    "hash": h,
                    "vector": vector,
                }
            )

    cache = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model_path": embedder.model_path,
        "entries": entries,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return cache


def load_cache(cache_path=None):
    cache_path = cache_path or _cache_path()
    if not cache_path.is_file():
        return None
    return json.loads(cache_path.read_text(encoding="utf-8"))


def is_stale(cases, cache):
    """True si le cache n'a pas (encore) de vecteur pour une
    formulation presente dans `cases` (cas ajoute/modifie depuis le
    dernier reindex). Sert au CLI pour avertir -- jamais pour
    recalculer silencieusement a la volee."""
    if cache is None:
        return bool(cases)
    cached = {(e["case_id"], e["hash"]) for e in cache.get("entries", [])}
    current = {(c["id"], _request_hash(r)) for c in cases for r in c["requests"]}
    return not current.issubset(cached)


def find_matches(query, cases=None, cache=None, embedder=None, top_k=3):
    """Retourne jusqu'a `top_k` tuples (cas, score, formulation la plus
    proche), meilleur score en premier. `score` est une similarite
    cosinus (en pratique ~[0, 1] pour ce type d'embedding).

    Ne construit ni ne rafraichit le cache -- appeler reindex()
    d'abord (le CLI avertit via is_stale() plutot que de recalculer
    silencieusement a chaque appel)."""
    cases = cases if cases is not None else load_cases()
    cache = cache if cache is not None else load_cache()
    if not cases or not cache or not cache.get("entries"):
        return []

    embedder = embedder or Embedder()
    _payload, normalized_query = extract_payload(query)
    query_vector = embedder.embed(normalized_query)

    by_case = {c["id"]: c for c in cases}
    best = {}
    for entry in cache["entries"]:
        case_id = entry["case_id"]
        if case_id not in by_case:
            continue  # cas retire du store depuis, cache pas encore reconstruit
        score = _cosine(query_vector, entry["vector"])
        if case_id not in best or score > best[case_id][0]:
            best[case_id] = (score, entry["request"])

    ranked = sorted(
        ((score, by_case[cid], req) for cid, (score, req) in best.items()),
        key=lambda t: t[0],
        reverse=True,
    )
    return [(case, score, req) for score, case, req in ranked[:top_k]]


# Seuil de confiance pour reutiliser un cas tel quel, sans passer par le
# LLM de generation. Calibre sur un tres petit echantillon (2 cas, voir
# discussion miniRAG) : vraies correspondances ~74-80% de similarite,
# demande sans rapport ~58-61% -- 0.70 laisse de la marge des deux
# cotes, mais reste a affiner sur un jeu de cas plus large avant d'y
# faire vraiment confiance.
DEFAULT_THRESHOLD = 0.70


def _threshold():
    raw = os.environ.get("SHSS_CASES_THRESHOLD")
    if raw is None or raw.strip() == "":
        return DEFAULT_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_THRESHOLD


def best_match(query, cases=None, cache=None, embedder=None, threshold=None):
    """Retourne (cas, score, payload) si le meilleur candidat depasse le
    seuil de confiance, sinon None. `payload` est le contenu entre
    guillemets de `query` s'il y en a un (voir extract_payload()),
    sinon None -- pertinent seulement pour un cas "gabarit"
    (case["input"] == "stdin"), ignore sinon.

    Seuil applique, par ordre de priorite : `threshold` (argument),
    puis case["threshold"] s'il existe, puis DEFAULT_THRESHOLD /
    SHSS_CASES_THRESHOLD. Un cas gabarit a souvent besoin d'un seuil
    plus eleve que la moyenne (voir add_case()) -- sans ca, plusieurs
    demandes sans rapport constatees en pratique (traduire un texte,
    compter des mots...) peuvent quand meme depasser un seuil generique,
    le gabarit de phrase pesant plus que le contenu une fois celui-ci
    normalise.

    Ne charge aucun modele si la base est vide : find_matches() sort
    avant d'instancier un Embedder des que `cases` ou `cache` est vide
    -- c'est ce qui garde une demande ordinaire, sans cas curate en
    jeu, gratuite."""
    matches = find_matches(query, cases=cases, cache=cache, embedder=embedder, top_k=1)
    if not matches:
        return None
    case, score, _matched_request = matches[0]
    if threshold is not None:
        seuil = threshold
    elif "threshold" in case:
        seuil = case["threshold"]
    else:
        seuil = _threshold()
    if score >= seuil:
        payload, _normalized = extract_payload(query)
        return case, score, payload
    return None
