import contextlib
import os
import re

TAG_RE = re.compile(r"#@\s*(.*?)\s*@#", re.DOTALL)

# "profil@" en tete du corps de la balise (#@pc-stats@ energie ... @#) :
# force SHSS_CASES_PROFILE pour cette resolution precise, sans avoir a
# l'exporter dans le shell avant. Ancre en debut de chaine : la syntaxe
# historique "#@ demande @#" (espace juste apres #@, TAG_RE l'a deja
# consomme) ne matche jamais ce prefixe, donc aucune demande existante
# n'est affectee.
_PROFILE_PREFIX_RE = re.compile(r"^([A-Za-z0-9_-]+)@")


def _split_profile(body: str):
    """Si `body` commence par 'profil@', retourne (profil, le reste
    sans ce prefixe, sans espace de bord). Sinon (None, body) tel quel."""
    m = _PROFILE_PREFIX_RE.match(body)
    if m:
        return m.group(1), body[m.end() :].strip()
    return None, body


@contextlib.contextmanager
def _profile_override(profile):
    """Force SHSS_CASES_PROFILE=profile pour la duree du bloc, puis
    restaure la valeur precedente (l'efface si elle n'existait pas) --
    ne fuit jamais vers la resolution suivante (important pour le REPL,
    qui reste le meme process d'une ligne a l'autre). No-op si
    `profile` est None."""
    if profile is None:
        yield
        return
    had_previous = "SHSS_CASES_PROFILE" in os.environ
    previous = os.environ.get("SHSS_CASES_PROFILE")
    os.environ["SHSS_CASES_PROFILE"] = profile
    try:
        yield
    finally:
        if had_previous:
            os.environ["SHSS_CASES_PROFILE"] = previous
        else:
            os.environ.pop("SHSS_CASES_PROFILE", None)


def find_requests(line: str):
    """Return the list of LLM request strings found in a line, in order
    (un eventuel prefixe 'profil@' est retire, jamais inclus)."""
    return [_split_profile(m.group(1))[1] for m in TAG_RE.finditer(line)]


def expand_line(line: str, resolver) -> str:
    """Replace every #@ ... @# tag in line with
    resolver(request_text, text_before_tag, text_after_tag)."""

    def _replace(m):
        profile, request = _split_profile(m.group(1))
        with _profile_override(profile):
            return resolver(request, line[: m.start()], line[m.end() :])

    return TAG_RE.sub(_replace, line)


def resolve_pending_tag(line: str, point: int, resolver):
    """Resolve the tag closest to `point`, whether it's still being typed
    (no closing '@#' yet) or already fully closed — used to react to a
    keypress (Ctrl-G) at any moment while editing the line, before Enter.

    Returns (new_line, new_point). If there is nothing to resolve at or
    before `point`, returns (line, point) unchanged.
    """
    before = line[:point]
    after = line[point:]

    idx = before.rfind("#@")
    if idx != -1 and "@#" not in before[idx:]:
        body = before[idx + 2 :].strip()
        profile, request = _split_profile(body)
        prefix = before[:idx]
        with _profile_override(profile):
            fragment = resolver(request, prefix, after)
        new_line = prefix + fragment + after
        return new_line, len(prefix) + len(fragment)

    last_match = None
    for m in TAG_RE.finditer(line):
        if m.end() <= point:
            last_match = m

    if last_match is None:
        return line, point

    prefix = line[: last_match.start()]
    suffix = line[last_match.end() :]
    profile, request = _split_profile(last_match.group(1))
    with _profile_override(profile):
        fragment = resolver(request, prefix, suffix)
    new_line = prefix + fragment + suffix
    new_point = len(prefix) + len(fragment) + (point - last_match.end())
    return new_line, new_point
