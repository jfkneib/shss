"""Interface graphique Tk pour la base de cas curates -- une autre
facade sur cases.py, au meme titre que cases_cli.py (aucune logique
metier ici, juste des boutons qui appellent les memes fonctions
testees). Optionnelle et auto-detectee : `shss-cases` sans argument
appelle try_run(), qui rend la main immediatement (False) si tkinter
n'est pas installe ou qu'aucun affichage n'est utilisable (ex: session
SSH sans X) -- l'appelant se rabat alors sur le CLI, sans erreur.

Tk n'est jamais importe au chargement du module (comme llama_cpp dans
llm.py) : seulement a l'interieur de try_run(), pour ne jamais faire
echouer un simple `import shss.cases_gui` sur une machine sans Tk.
"""

import queue
import threading


def _select_all(widget):
    widget.tag_remove("sel", "1.0", "end")
    widget.tag_add("sel", "1.0", "end-1c")
    widget.mark_set("insert", "end-1c")
    widget.see("insert")


def _add_text_context_menu(tk, widget):
    """Menu clic-droit (Couper/Copier/Coller/Tout sélectionner) sur un
    tk.Text -- Ctrl-C/X/V marchent deja nativement des que le widget a
    le focus clavier, mais rien n'indique a l'oeil que c'est possible
    sur un tk.Text brut (pas de menu contextuel par defaut, contrairement
    a un champ de texte natif de l'OS).

    Rebranche aussi Ctrl-A sur "tout selectionner" : par defaut, un
    tk.Text suit la convention Emacs (Ctrl-A = debut de ligne, pas
    selection) -- source d'un vrai incident constate : coller un
    script en pensant avoir tout selectionne au prealable l'insere en
    plein milieu de l'ancien contenu, sans le remplacer, et corrompt
    le script (deux "if" imbriques n'importe comment, syntaxe cassee)."""
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Couper", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Copier", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Coller", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_separator()
    menu.add_command(label="Tout sélectionner (Ctrl-A)", command=lambda: _select_all(widget))

    def _popup(event):
        menu.tk_popup(event.x_root, event.y_root)

    widget.bind("<Button-3>", _popup)

    def _on_ctrl_a(_event):
        _select_all(widget)
        return "break"  # empeche le "debut de ligne" Emacs par defaut

    widget.bind("<Control-a>", _on_ctrl_a)


def try_run():
    """Tente d'ouvrir la fenetre et tourne jusqu'a sa fermeture.
    Retourne True si elle a pu s'ouvrir, False sinon (tkinter absent,
    ou `tk.Tk()` echoue faute d'affichage) -- dans ce cas rien n'a ete
    montre a l'ecran, l'appelant peut se rabattre sur autre chose."""
    try:
        import tkinter as tk
    except ImportError:
        return False

    try:
        root = tk.Tk()
    except tk.TclError:
        return False

    _App(root)
    root.mainloop()
    return True


class _App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        from . import cases as cases_module

        self._tk = tk
        self._ttk = ttk
        self._cases_module = cases_module
        self.root = root
        self._queue = queue.Queue()
        self._busy = False

        root.title("shss-cases — base de cas curatés")
        root.geometry("820x520")
        root.minsize(600, 400)

        self._build_layout()
        self._refresh_list()

    # ------------------------------------------------------------ layout

    def _build_layout(self):
        tk, ttk = self._tk, self._ttk

        body = ttk.Frame(self.root, padding=10)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(left, text="Cas curatés", font=("", 10, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(left, width=30, exportselection=False)
        self.listbox.pack(fill="y", expand=True, pady=(4, 0))
        self.listbox.bind("<<ListboxSelect>>", lambda _e: self._show_details(self._selected_case()))
        # Double-clic = raccourci direct vers "Modifier..." : le panneau
        # de droite n'est qu'un apercu en lecture seule (voir plus bas),
        # sans ca la seule facon d'editer est de retrouver le bouton.
        self.listbox.bind("<Double-Button-1>", lambda _e: self._open_edit())

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="Détails (lecture seule — double-clic ou « Modifier… » pour éditer)", font=("", 10, "bold")).pack(
            anchor="w"
        )
        self.details = tk.Text(right, wrap="word", state="disabled", bg="#f5f5f5")
        self.details.pack(fill="both", expand=True, pady=(4, 0))

        actions = ttk.Frame(self.root, padding=(10, 0, 10, 4))
        actions.pack(fill="x")
        ttk.Button(actions, text="Ajouter…", command=self._open_add).pack(side="left")
        ttk.Button(actions, text="Modifier…", command=self._open_edit).pack(side="left", padx=4)
        ttk.Button(actions, text="Supprimer", command=self._remove_selected).pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(actions, text="Tester une demande…", command=self._open_test).pack(side="left")
        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=8)
        self.reindex_btn = ttk.Button(actions, text="Réindexer", command=self._reindex)
        self.reindex_btn.pack(side="left")
        self.model_btn = ttk.Button(actions, text="Modèle d'embeddings…", command=self._open_model)
        self.model_btn.pack(side="left", padx=4)

        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=140)
        self.status = ttk.Label(bottom, text="Prêt.", foreground="#555")
        self.status.pack(side="left")

    # ------------------------------------------------------------ state

    def _set_status(self, text):
        self.status.config(text=text)

    def _refresh_list(self):
        self.cases = self._cases_module.load_cases()
        self.listbox.delete(0, "end")
        for case in self.cases:
            self.listbox.insert("end", case["id"])
        self._show_details(None)
        n = len(self.cases)
        self._set_status(f"{n} cas curaté{'s' if n != 1 else ''}." if n else "Base vide.")

    def _selected_case(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.cases[sel[0]]

    def _show_details(self, case):
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        if case is not None:
            lines = [f"id : {case['id']}", "", "formulations :"]
            lines += [f"  • {r}" for r in case["requests"]]
            if case.get("note"):
                lines += ["", f"note : {case['note']}"]
            if case.get("input") == "stdin":
                lines += ["", "gabarit : oui -- le contenu entre guillemets est transmis au script sur stdin"]
            if "threshold" in case:
                lines += ["", f"seuil propre a ce cas : {case['threshold']}"]
            lines += ["", "script :", "-" * 40, case["script"]]
            self.details.insert("1.0", "\n".join(lines))
        self.details.config(state="disabled")

    # ------------------------------------------------------------ actions

    def _open_add(self):
        _CaseDialog(self, existing=None)

    def _open_edit(self):
        case = self._selected_case()
        if case is None:
            self._set_status("Sélectionne d'abord un cas à modifier.")
            return
        _CaseDialog(self, existing=case)

    def _remove_selected(self):
        from tkinter import messagebox

        case = self._selected_case()
        if case is None:
            self._set_status("Sélectionne d'abord un cas à supprimer.")
            return
        if not messagebox.askyesno("Confirmer", f"Retirer le cas « {case['id']} » ?", parent=self.root):
            return
        cases = self._cases_module.remove_case(self._cases_module.load_cases(), case["id"])
        self._cases_module.save_cases(cases)
        self._set_status(f"Cas « {case['id']} » retiré.")
        self._refresh_list()

    def _open_test(self):
        _TestDialog(self)

    def _open_model(self):
        _ModelDialog(self)

    def _reindex(self):
        cases = self._cases_module.load_cases()
        if not cases:
            self._set_status("Base vide, rien à indexer.")
            return

        def work():
            return self._cases_module.reindex(cases)

        def done(cache):
            self._set_status(f"{len(cache['entries'])} formulation(s) indexée(s) pour {len(cases)} cas.")

        self._run_background("Réindexation en cours…", work, done)

    # ------------------------------------------------------------ background work

    def _run_background(self, message, work, on_done):
        if self._busy:
            return
        self._busy = True
        self._set_status(message)
        self.progress.pack(side="left", padx=(0, 8), before=self.status)
        self.progress.start(12)
        for btn in (self.reindex_btn, self.model_btn):
            btn.state(["disabled"])

        def runner():
            try:
                result = work()
                self._queue.put(("ok", result))
            except Exception as exc:  # noqa: BLE001 -- affiche toute erreur, ne masque rien
                self._queue.put(("error", exc))

        threading.Thread(target=runner, daemon=True).start()
        self.root.after(100, lambda: self._poll(on_done))

    def _poll(self, on_done):
        try:
            status, payload = self._queue.get_nowait()
        except queue.Empty:
            self.root.after(100, lambda: self._poll(on_done))
            return

        self.progress.stop()
        self.progress.pack_forget()
        for btn in (self.reindex_btn, self.model_btn):
            btn.state(["!disabled"])
        self._busy = False

        if status == "error":
            self._set_status(f"Erreur : {payload}")
        else:
            on_done(payload)


class _CaseDialog:
    """Fenêtre d'ajout ou de modification -- même formulaire pour les
    deux, ne diffère que par ce qui est pré-rempli et l'appel final
    (add_case vs update_case, déjà testés dans cases.py)."""

    def __init__(self, app: _App, existing):
        tk, ttk = app._tk, app._ttk
        self.app = app
        self.existing = existing

        win = tk.Toplevel(app.root)
        win.title("Modifier un cas" if existing else "Ajouter un cas")
        win.geometry("560x720")
        win.minsize(480, 560)
        win.transient(app.root)
        self.win = win

        # Un Toplevel n'a pas garanti le focus clavier a l'ouverture sur
        # tous les gestionnaires de fenetres -- sans ca, taper semblait
        # ne rien faire (les touches allaient ailleurs, ou nulle part).
        win.lift()
        win.focus_force()
        win.grab_set()  # modal : force a fermer cette fenetre avant de revenir a la liste

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Identifiant").pack(anchor="w")
        self.id_entry = ttk.Entry(frame)
        self.id_entry.pack(fill="x")
        if existing:
            self.id_entry.insert(0, existing["id"])
            self.id_entry.config(state="disabled")  # l'id ne se modifie pas ici

        ttk.Label(frame, text="Formulations d'exemple (une par ligne)").pack(anchor="w", pady=(8, 0))
        self.requests_text = tk.Text(frame, height=5)
        self.requests_text.pack(fill="x")
        _add_text_context_menu(tk, self.requests_text)
        if existing:
            self.requests_text.insert("1.0", "\n".join(existing["requests"]))

        ttk.Label(frame, text="Note (optionnel)").pack(anchor="w", pady=(8, 0))
        self.note_entry = ttk.Entry(frame)
        self.note_entry.pack(fill="x")
        if existing and existing.get("note"):
            self.note_entry.insert(0, existing["note"])

        # ttk.Checkbutton n'accepte pas -wraplength en argument direct
        # sur toutes les versions de Tk (leve TclError) -- le texte long
        # va dans un Label separe (qui, lui, le supporte), la case a
        # cocher garde un intitule court.
        self.stdin_var = tk.BooleanVar(value=bool(existing and existing.get("input") == "stdin"))
        ttk.Checkbutton(frame, text="Cas « gabarit »", variable=self.stdin_var).pack(anchor="w", pady=(8, 0))
        ttk.Label(
            frame,
            text="Le contenu entre guillemets de la demande varie à chaque fois et est "
            "transmis au script sur son entrée standard (ex: sys.stdin.read()).",
            wraplength=460,
            foreground="#666",
        ).pack(anchor="w", fill="x")

        threshold_row = ttk.Frame(frame)
        threshold_row.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Label(threshold_row, text="Seuil de confiance propre à ce cas (vide = seuil global) :").pack(
            side="left"
        )
        self.threshold_entry = ttk.Entry(threshold_row, width=6)
        self.threshold_entry.pack(side="left", padx=(6, 0))
        if existing and "threshold" in existing:
            self.threshold_entry.insert(0, str(existing["threshold"]))

        # Boutons et message d'erreur ancres en bas AVANT la zone de
        # script : avec pack(side="bottom"), ils restent toujours
        # visibles et cliquables (donc "Valider" toujours atteignable),
        # meme si la fenetre est redimensionnee petite -- c'est la zone
        # de script (empaquetee en dernier, fill+expand) qui absorbe la
        # difference, jamais les boutons qui se retrouvent hors ecran.
        buttons = ttk.Frame(frame)
        buttons.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Charger un fichier…", command=self._load_file).pack(side="left")
        ttk.Button(buttons, text="Aide", command=lambda: _HelpDialog(self.app, self.win)).pack(side="left", padx=4)
        ttk.Button(buttons, text="Annuler", command=win.destroy).pack(side="right")
        ttk.Button(buttons, text="Valider", command=self._submit).pack(side="right", padx=4)

        self.error_label = ttk.Label(frame, foreground="#b33")
        self.error_label.pack(side="bottom", anchor="w", pady=(4, 0))

        ttk.Label(frame, text="Script").pack(anchor="w", pady=(8, 0))
        self.script_text = tk.Text(frame, height=12, font=("Courier", 10))
        self.script_text.pack(fill="both", expand=True)
        _add_text_context_menu(tk, self.script_text)
        if existing:
            self.script_text.insert("1.0", existing["script"])
        else:
            self.script_text.insert("1.0", "#!/usr/bin/env bash\n")

        # Focus initial sur le script : c'est le champ le plus souvent
        # a modifier, et ca confirme visuellement (curseur clignotant)
        # que la fenetre a bien le clavier.
        self.script_text.focus_set()

    def _load_file(self):
        from tkinter import filedialog

        path = filedialog.askopenfilename(parent=self.win, title="Choisir un script")
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.script_text.delete("1.0", "end")
        self.script_text.insert("1.0", content)

    def _submit(self):
        cm = self.app._cases_module
        case_id = (self.existing["id"] if self.existing else self.id_entry.get()).strip()
        requests = [r for r in self.requests_text.get("1.0", "end").splitlines() if r.strip()]
        script = self.script_text.get("1.0", "end")
        note = self.note_entry.get().strip()
        input_mode = "stdin" if self.stdin_var.get() else ""
        threshold_raw = self.threshold_entry.get().strip()

        try:
            threshold = float(threshold_raw) if threshold_raw else ("" if self.existing else None)
        except ValueError:
            self.error_label.config(text=f"seuil invalide : {threshold_raw!r} (un nombre entre 0 et 1)")
            return

        try:
            if self.existing:
                cases = cm.update_case(
                    cm.load_cases(),
                    case_id,
                    requests=requests,
                    script=script,
                    note=note,
                    input_mode=input_mode,
                    threshold=threshold,
                )
            else:
                if not case_id:
                    raise ValueError("un identifiant est requis")
                cases = cm.add_case(
                    cm.load_cases(),
                    case_id,
                    requests,
                    script,
                    note=note,
                    input_mode=input_mode or None,
                    threshold=threshold,
                )
        except (ValueError, KeyError) as exc:
            self.error_label.config(text=str(exc))
            return

        cm.save_cases(cases)
        self.app._set_status(f"Cas « {case_id} » enregistré — pense à Réindexer.")
        self.app._refresh_list()
        self.win.destroy()


class _TestDialog:
    def __init__(self, app: _App):
        tk, ttk = app._tk, app._ttk
        self.app = app

        win = tk.Toplevel(app.root)
        win.title("Tester une demande")
        win.geometry("480x360")
        win.transient(app.root)

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Demande en langage naturel").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(4, 8))
        self.entry = ttk.Entry(row)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _e: self._run())
        ttk.Button(row, text="Tester", command=self._run).pack(side="left", padx=(6, 0))

        self.results = tk.Text(frame, state="disabled", wrap="word")
        self.results.pack(fill="both", expand=True)
        self.entry.focus_set()

    def _run(self):
        cm = self.app._cases_module
        query = self.entry.get().strip()
        if not query:
            return

        cases = cm.load_cases()
        cache = cm.load_cache()
        lines = []
        if cm.is_stale(cases, cache):
            lines.append("(cache pas à jour -- Réindexer d'abord pour un résultat fiable)\n")

        payload, _normalized = cm.extract_payload(query)
        if payload is not None:
            lines.append(f"contenu entre guillemets détecté : {payload!r}\n")

        try:
            matches = cm.find_matches(query, cases=cases, cache=cache, top_k=5)
        except FileNotFoundError as exc:
            matches = None
            lines.append(f"Erreur : {exc}")

        if matches is not None:
            if not matches:
                lines.append("Aucun match (base ou cache vide).")
            else:
                for case, score, matched_request in matches:
                    seuil = case.get("threshold", cm._threshold())
                    marque = "→ réutilisé" if score >= seuil else "en dessous du seuil"
                    lines.append(
                        f"{score * 100:5.1f}%  {case['id']}  (seuil {seuil * 100:.0f}%, {marque})\n"
                        f"        proche de : « {matched_request} »"
                    )

        self.results.config(state="normal")
        self.results.delete("1.0", "end")
        self.results.insert("1.0", "\n".join(lines))
        self.results.config(state="disabled")


class _ModelDialog:
    def __init__(self, app: _App):
        tk, ttk = app._tk, app._ttk
        self.app = app
        cm = app._cases_module

        win = tk.Toplevel(app.root)
        win.title("Modèle d'embeddings")
        win.geometry("440x160")
        win.transient(app.root)
        self.win = win

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        path = cm.curated_embed_model_path()
        import os

        present = os.path.isfile(path)
        state = f"déjà présent :\n{path}" if present else f"pas encore téléchargé (~{cm.CURATED_EMBED_MODEL_SIZE_MB} Mo)"
        ttk.Label(frame, text=state, wraplength=400, justify="left").pack(anchor="w")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        self.dl_btn = ttk.Button(buttons, text="Télécharger", command=self._download)
        self.dl_btn.pack(side="left")
        if present:
            self.dl_btn.state(["disabled"])
        ttk.Button(buttons, text="Fermer", command=win.destroy).pack(side="right")

        self.status = ttk.Label(frame, text="")
        self.status.pack(anchor="w", pady=(8, 0))

    def _download(self):
        cm = self.app._cases_module
        self.dl_btn.state(["disabled"])
        self.status.config(text="Téléchargement en cours…")

        def work():
            return cm.download_embedding_model()

        def done(path):
            self.status.config(text=f"Installé : {path}")

        self.app._run_background("Téléchargement du modèle d'embeddings…", work, done)


_HELP_TEXT = """CHAMPS DU FORMULAIRE

Identifiant
  Court, stable, ne se modifie pas une fois le cas créé (« Supprimer »
  puis « Ajouter » pour en changer).

Formulations d'exemple
  Une par ligne. Plusieurs variantes de la même demande aident le
  matching à mieux reconnaître le cas — plus il y en a, mieux c'est.

Note
  Libre, pour toi (et pour qui relira ce cas plus tard) : pourquoi ce
  cas existe, ses limites connues. N'influence jamais le matching.

Cas « gabarit »
  À cocher quand le contenu entre guillemets de la demande change à
  chaque fois (ex : corrige ma ligne : "...") plutôt qu'une question
  toujours identique. Ce contenu est retiré du calcul de similarité
  (le matching se base sur la formulation autour) et transmis au
  script sur son entrée standard au moment de l'exécution — jamais
  collé dans le code, aucun risque d'injection.

Seuil de confiance
  Vide = seuil global de la base (SHSS_CASES_THRESHOLD, 70 % par
  défaut). Un chiffre entre 0 et 1 fixe un seuil propre à CE cas.
  Un cas gabarit a souvent besoin d'un seuil plus élevé : une fois le
  contenu entre guillemets normalisé, il ne reste que la formulation
  pour distinguer les cas, et certaines formulations très génériques
  ("corrige ma commande ... : \"...\"") matchent large. Utilise
  « Tester une demande… » pour vérifier avant de choisir.

Script
  Le programme exécuté quand ce cas est réutilisé — bash, python,
  n'importe quel langage avec un shebang valide. Jamais d'arguments en
  ligne de commande (pas de sys.argv/$1) : ce dont il a besoin lui
  arrive via les variables d'environnement ci-dessous, ou via son
  entrée standard pour un cas gabarit.


VARIABLES TOUJOURS DISPONIBLES POUR UN SCRIPT (gabarit ou pas)

  SHSS_REQUEST       la demande complète d'origine
  SHSS_PREFIX        le bash avant la balise #@ ... @# sur la ligne
  SHSS_SUFFIX        le bash après la balise sur la ligne
  SHSS_MATCH_SCORE   le score de similarité qui a fait matcher ce cas
  SHSS_CASE_ID       l'identifiant de ce cas

  bash   : "$SHSS_REQUEST"
  python : os.environ["SHSS_REQUEST"]


RAPPELER LE LLM DEPUIS UN SCRIPT

Un script peut lui-même demander une génération au LLM pour une
sous-partie qu'il ne sait pas traiter :

  bin/shss-resolve-inline "#@ ta demande @#" 60 | head -1

La première ligne de sortie est le texte généré, rien n'est exécuté.
Utile pour combiner logique déterministe et génération — à utiliser
avec parcimonie, ça recharge un modèle à chaque appel (quelques
secondes).


PLUSIEURS BASES SÉPARÉES (SYSTÈME, DEV, AUTRE…)

  export SHSS_CASES_PROFILE=dev

Fait pointer shss-cases (et la résolution) vers
~/.shss/profiles/dev/ — une seule variable, le cache d'embeddings
suit automatiquement. Séparer les bases réduit aussi le risque de faux
positif entre cas sans rapport.
"""


class _HelpDialog:
    def __init__(self, app: _App, parent_win):
        tk, ttk = app._tk, app._ttk

        win = tk.Toplevel(parent_win)
        win.title("Aide — shss-cases")
        win.geometry("560x600")
        win.transient(parent_win)
        win.lift()
        win.focus_force()
        win.grab_set()

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, wrap="word", state="normal")
        text.pack(fill="both", expand=True)
        text.insert("1.0", _HELP_TEXT)
        text.config(state="disabled")
        _add_text_context_menu(tk, text)  # copier reste possible, meme en lecture seule

        ttk.Button(frame, text="Fermer", command=win.destroy).pack(anchor="e", pady=(8, 0))
