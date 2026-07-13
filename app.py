# -*- coding: utf-8 -*-
"""
Kali — Gestionnaire de fenêtres multi-comptes pour Dofus
Interface inspirée de Windows 11. Aucune dépendance externe (stdlib uniquement).

Fonctionnalités :
- Détection automatique des fenêtres Dofus ouvertes
- Ordre d'initiative réorganisable (boutons ▲ ▼ ou glisser-déposer)
- Raccourcis clavier GLOBAUX (fonctionnent même en jeu) :
    * Perso suivant / précédent (cycle dans l'ordre d'initiative)
    * Aller directement au perso 1..8
- Clic sur un perso = bascule sur sa fenêtre
- Toujours au premier plan (optionnel)
- Configuration sauvegardée automatiquement (config.json à côté de l'exe)
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import font as tkfont
from tkinter import messagebox

# --- Mise à jour automatique via GitHub ---
# Le compte a été renommé Skiiouw -> Skiouw-Dev : on essaie la nouvelle
# adresse en premier, l'ancienne en secours (redirection éventuelle).
UPDATE_URLS = [
    "https://raw.githubusercontent.com/Skiouw-Dev/Kali-Dofus/main/app.py",
    "https://raw.githubusercontent.com/Skiiouw/Kali-Dofus/main/app.py",
]


def parse_remote_version(source):
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source)
    return m.group(1) if m else None


def version_tuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)

# ----------------------------------------------------------------------------
# API Windows (ctypes, aucune dépendance)
# ----------------------------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetProcessDPIAware()

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
IsIconic = user32.IsIconic
ShowWindow = user32.ShowWindow
SetForegroundWindow = user32.SetForegroundWindow
GetForegroundWindow = user32.GetForegroundWindow
GetAncestor = user32.GetAncestor
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
AttachThreadInput = user32.AttachThreadInput
BringWindowToTop = user32.BringWindowToTop
RegisterHotKey = user32.RegisterHotKey
UnregisterHotKey = user32.UnregisterHotKey
GetMessageW = user32.GetMessageW
PostThreadMessageW = user32.PostThreadMessageW
IsWindow = user32.IsWindow

OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
GetClassNameW = user32.GetClassNameW
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

SW_RESTORE = 9
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

MOD_NOREPEAT = 0x4000

# Codes de touches virtuelles utilisables comme raccourcis
VK_CODES = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
    "Tab": 0x09, "²": 0xDE, "PageUp": 0x21, "PageDown": 0x22,
    "Inser": 0x2D, "Suppr": 0x2E, "Début": 0x24, "Fin": 0x23,
    "Pavé0": 0x60, "Pavé1": 0x61, "Pavé2": 0x62, "Pavé3": 0x63,
    "Pavé+": 0x6B, "Pavé-": 0x6D, "Pavé*": 0x6A, "Pavé/": 0x6F,
}

APP_TITLE = "Kali"
APP_VERSION = "3.5"

# Style par classe : (glyphe d'arme stylisé, couleur) — dessins génériques,
# aucune ressource Ankama. Détecté depuis le titre "Nom - Classe - ...".
CLASS_STYLE = {
    "feca":       ("\u26e8", "#5ec8a8"),   # bouclier
    "osamodas":   ("\u265e", "#e0955a"),   # créature
    "enutrof":    ("\u26cf", "#e6c84f"),   # pelle/pioche
    "sram":       ("\u2620", "#a67fd4"),   # dague/ombre
    "xelor":      ("\u231b", "#5a9de0"),   # sablier
    "ecaflip":    ("\u2684", "#e05a5a"),   # dé
    "eniripsa":   ("\u271a", "#f08fc0"),   # fiole/soin
    "iop":        ("\u2694", "#e07a3c"),   # épée
    "cra":        ("\u27b9", "#7fd45e"),   # flèche
    "sadida":     ("\u2740", "#4faf6e"),   # ronce/fleur
    "sacrieur":   ("\u2665", "#d44f5e"),   # sang
    "pandawa":    ("\u262f", "#d4b98a"),   # tonneau/équilibre
    "roublard":   ("\u2734", "#9aa0a6"),   # bombe
    "zobal":      ("\u263b", "#b08968"),   # masque
    "steamer":    ("\u2699", "#5ad4d4"),   # mécanisme
    "eliotrope":  ("\u25ce", "#7ab8ff"),   # portail
    "huppermage": ("\u2726", "#b06fe0"),   # rune
    "ouginak":    ("\u263e", "#c98a5a"),   # croc
    "forgelance": ("\u2699", "#8a9ab8"),   # lance
}
CLASS_DEFAULT = ("\u25c6", "#6f7276")

# Abréviations affichées quand aucune icône officielle n'est installée
CLASS_ABBR = {
    "feca": "Féca", "osamodas": "Osa", "enutrof": "Enu", "sram": "Sram",
    "xelor": "Xel", "ecaflip": "Eca", "eniripsa": "Eni", "iop": "Iop",
    "cra": "Crâ", "sadida": "Sadi", "sacrieur": "Sacri", "pandawa": "Panda",
    "roublard": "Roub", "zobal": "Zobal", "steamer": "Stea",
    "eliotrope": "Elio", "huppermage": "Hupp", "ouginak": "Ougi",
    "forgelance": "Forge",
}

# ---------------------------------------------------------------------------
# Icônes des jetons : capturées directement sur les fenêtres Dofus.
# Chaque fenêtre du jeu porte l'icône de sa classe -> on la lit via l'API
# Windows et on la convertit en image tkinter. Zéro fichier, zéro dépendance.
# ---------------------------------------------------------------------------
gdi32 = ctypes.windll.gdi32
_WICON_CACHE = {}

# Pillow : anti-aliasing de qualité pour les jetons (embarqué dans l'exe).
try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long), ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


def get_window_hicon(hwnd):
    """Handle de l'icône de la fenêtre (priorité aux grandes icônes)."""
    res = wt.DWORD()
    for wparam in (1, 2, 0):  # ICON_BIG, ICON_SMALL2, ICON_SMALL
        if user32.SendMessageTimeoutW(hwnd, 0x7F, wparam, 0,
                                      0x2, 200, ctypes.byref(res)) and res.value:
            return res.value
    get_cls = getattr(user32, "GetClassLongPtrW", user32.GetClassLongW)
    return get_cls(hwnd, -14) or get_cls(hwnd, -34)


def _hicon_to_rgba(hicon, cap):
    """Rend l'icône dans un buffer BGRA `cap`x`cap`. Retourne bytes ou None."""
    try:
        hdc = user32.GetDC(0)
        mem = gdi32.CreateCompatibleDC(hdc)
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth, bmi.biHeight = cap, -cap
        bmi.biPlanes, bmi.biBitCount = 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0,
                                      ctypes.byref(bits), None, 0)
        oldobj = gdi32.SelectObject(mem, hbmp)
        # fond noir transparent (alpha=0) : on lit l'alpha réel de l'icône
        user32.DrawIconEx(mem, 0, 0, hicon, cap, cap, 0, None, 3)
        raw = ctypes.string_at(bits.value, cap * cap * 4)
        gdi32.SelectObject(mem, oldobj)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(0, hdc)
        return raw
    except Exception:
        return None


def window_icon_pil(hwnd, size):
    """Image Pillow RGBA de l'icône (ronde, anti-aliasée), ou None.
    Rendu à 4x puis réduit en LANCZOS = qualité maximale."""
    if not PIL_OK or hwnd is None:
        return None
    cap = min(256, max(64, size * 4))
    raw = None
    hicon = get_window_hicon(hwnd)
    if hicon:
        raw = _hicon_to_rgba(hicon, cap)
    if raw is None:
        return None
    # BGRA -> RGBA
    img = Image.frombuffer("RGBA", (cap, cap), raw, "raw", "BGRA", 0, 1)
    # certaines icônes ont un alpha nul partout (mal déclaré) : corrige
    if img.getchannel("A").getbbox() is None:
        img.putalpha(255)
    # masque circulaire anti-aliasé (rendu 4x puis réduit)
    big = size * 4
    img = img.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    img.putalpha(mask)
    img = img.resize((size, size), Image.LANCZOS)
    return img


_TOKEN_CACHE = {}


def make_token_pil(hwnd, R, ring_hex, active, accent_hex="#4cc2ff",
                   bg_hex="#16161e"):
    """Jeton complet Pillow (halo + anneau de classe + icône), tout
    anti-aliasé. Retourne un ImageTk.PhotoImage prêt à afficher, ou None.
    Mis en cache par (hwnd, R, classe, actif) : recalcul uniquement si l'un
    de ces paramètres change -> changement de perso actif quasi instantané."""
    if not PIL_OK:
        return None
    key = (hwnd, R, ring_hex, active)
    if key in _TOKEN_CACHE:
        return _TOKEN_CACHE[key]
    halo = 9
    S = 2 * (R + halo) + 2
    SS = 4
    N = S * SS
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = N / 2
    ring = tuple(int(ring_hex[i:i+2], 16) for i in (1, 3, 5)) + (255,)
    accent = tuple(int(accent_hex[i:i+2], 16) for i in (1, 3, 5))
    bg = tuple(int(bg_hex[i:i+2], 16) for i in (1, 3, 5)) + (255,)

    def circle(radius, fill=None, outline=None, width=1):
        d.ellipse((c - radius, c - radius, c + radius, c + radius),
                  fill=fill, outline=outline, width=width)

    if active:
        # halo bleu marqué : anneaux d'alpha décroissant + liseré vif
        for k in range(halo, 0, -1):
            a = int(200 * (k / halo))
            circle((R + k) * SS, outline=accent + (a,), width=2 * SS)
        circle((R + 2) * SS, outline=accent + (255,), width=SS)
    ring_w = (3 if active else 2) * SS
    circle(R * SS, fill=bg)                      # disque de fond
    circle(R * SS, outline=ring, width=ring_w)   # anneau de classe

    # icône au centre
    ico = window_icon_pil(hwnd, int((R - 3) * 2) * SS // SS)
    if ico is not None:
        ico = ico.resize(((R - 2) * 2 * SS, (R - 2) * 2 * SS), Image.LANCZOS)
        im.alpha_composite(ico, (int(c - ico.width / 2),
                                 int(c - ico.height / 2)))

    im = im.resize((S, S), Image.LANCZOS)
    tkimg = ImageTk.PhotoImage(im)
    _TOKEN_CACHE[key] = tkimg
    return tkimg


def normalize_class(txt):
    t = txt.strip().lower()
    for a, b in (("â", "a"), ("é", "e"), ("è", "e"), ("ê", "e"), ("ï", "i")):
        t = t.replace(a, b)
    return t
# Icône embarquée (PNG base64) — utilisée pour la barre de titre
# et la barre des tâches, identique au .ico de l'exe et du tray
ICON_PNG_16 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADVUlEQVR4nFWTTWhcVRiG3++7586dn8zcpJkkg+lEpSZUKUo0VhELEkypaZHSRdGFWcRdQGoWFgzCGHFh3YiKliLVhRWMVKWh1BotttgSF3EoGoUYsVUcbZtMMjPJzL0z95zzuQiIPvt39bwPoSCMabIFkczVIkaaN292wjoQC8J/IIaADeLdPZWdD+Cr14jWCwVhAoCDS7K7dPL4qcr8bL/oCMQKIhaw5t81sQOxBqQU/KF913rHjoyfGaSL6ohI++XJN0//dWo6b63VEjXZhKE4ngf2kgARJGpC1+tg1yFOtNmNxSt32mZ4ekJkl7o2j5FacS5vrWh2PeU/tB/+/UOoFhdQLX4NWIPEjkF07T2E1moVK19+wLpe1bXiXOdvX0w8yeHKraw0QyHXJRtswh/aizuem0T7g/ugN9ahMlncNfU+8uOTiCq3YBobYBUj2wyltf53ltlRBkREIiBHwYYN6IqGbdRAAux44T349/bj11ensHr+JFQqAxILYiZWjlFiLREBkTZkNmtoaYPIUQiCED3PHkN6eA9+Of4ufp85BpXphG7UoYMGOa0WmIiUw4A2gq72NtPx+CHkBnZKTxOSPXAYyb48NhZ/Qnn+Q+waenjLpRUkFOnNRDYeBAFUzPMkCEOMPvpIOPD865yLs+nPQZc78gjqLSAbwZ06CsTTgImgjUVvdzb67NvvY2drNVJB0KR0KomZ2XNJdXHI6R17GdufHsPyzOf4udQGbMvB//QVxMrLsLEUIBakWzbZdzcPvDgiTMwiInC9OGStBA5qUEojU13GtktT4HQnGgfegJvpQsIRxBNJKKXEdV2AWdga7UBEBAAcF5zMQPkK4vci9scC/AsvIcoNYmX0LRg3BTF661zWitWRo7yO7grFPBIdgeMpVBfO4/rbZVSLC0B7F1JLZwGjEXXdA+33wSsvwVgrFPMo1tGzrvr2YK5032M3NhYv50RHeu3KGVq98DHYi4PjSWgDJH78BAkTQWJtiMgR0k2VHhyu3v5Ex6x6h6h88Ad5ih33o8p3s71WRyBHAdZCrN2KiRkAAVaDXRf+7tEb+WeOjp8gKlGhIDw9TXZCJHf9m/r+1sqfWUAB1v4vZzALoOFlb1vbPpw+d4KoVCgI/wOLWZJSyhb/iAAAAABJRU5ErkJggg=="
ICON_PNG_20 = "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAET0lEQVR4nH2Ua4iVVRSGn7W/yzlzd0advIzXGMoL0020+hGokGJlGngtqTBDDIoKTCk9HdOSIjIzwiCiH5UoaRJeKkurHyMpCSJGjDQlOk6Ox3HO/Xzn+/bqxxlHhWz/3Oz17L3W++5XABIJNcmkWFU1y+GOQoZ6ioDLf68QiENNHdmVcHKKSDmRSJhkMmkloWqSIvaxP3ROz8FDm64c2zdZS4GLMaA3AYqARphYLKpvm3566KxH3tjTJrsSqkYAFnTo7M4Ptxzo+mITYTGPGFMpArAWVR3gYJzKvoLaCMfzGbl4DaNWvLJkz52yQ3aq+u+/u+9E59tPT1QxZROLe7ZUwJaKIOBU1SJOf++qRPk0ai3iujjV9Wg5CG0h64x78eOuB9cvnujuh8npE4dvD4tZ9RqHeWHmMo3THmbw9LloABe+2kLxfAfixdAopOXJDcRHDqfY1U3Xjs2I47pqI02f/GlkR2rxVJO/RIMGxYEetVyiZnwbwx5dSPNDC/EGNaPWEuX6aFn2OqOfeZ7B0xeQ/f0otlQAMSBGNShqoYdBxnGwA/PqH5QNCpT7IsJ0CAhh+jK3zH2OEYtWEmaVM2+uIvXzLpyqWlBbGaiIuB6RuVE8QcQgxsE4DsZ3CTMpGqfOYuzKTRgPLuz4gEuHPiM2eASoRUQwpoKxEXKD00qlElExT1AuEwiEhTLu2DZGLnmVqNqh6+tdnNm+Gqe6njCXrTzCOAS5nAzqd8I1oBjGDG+O/HnPStOtk3WEg4ZxZdQLb+E11pHv/IvUd1u5bVIb4rqgiqriej5+NCZKeV4siq4DKrD1vXd620fPrJ7qF0oThxDkI1+KZR/CAOpiOJ9sh3gtRCGIoKo4nk+jL+Gqj3YPP9N9XcsCPP7UisFVE+6VPXfNrBo+fzk2W+To/sOkYq245T6avn0JL9WBerWgEQCO6+EEuYjJM2XSUvSaKGophir/HPqSTPdZKQpSdGISb98mQccRydaMlnNTV0s29CSf6ZVcviD5fE4ymYz09PQ4V4W5QWXHCG51bUXhKETU4mjI0CPr8XpOYVumkJ6xDpcI14DjuLiui+d5A7/eRBGGfoUU0CjEeHHcBhevzkFjtZhciqYfXkPS5ylMWsTlB9ZBFFbOq1bKVVUFcb0hZE2sSgFBFfFi5P48SffenWgA4eULaHUj3sXTNP2YoNA6G3V9yo3j8Ho7wa9G1Yr4cfEayLh3w6nOCfd1OAc+adVyKXJrBrl9v31Pb/s3/eFQg+P5WIlTdf5Xqs7+UrnbrwG/CrVhJILUTbz/4rhmjrkvixTmn9Y1QVfH7nOfb3SttSrGUYyAQpTLcDUYQzH9frBI0IeqiqBOy9K1NM9btnazSK/bH7B75h7XJ/yW1g3p4wfH2yCQ/w9YwFpMzKe+bcbfQ+cs3rj3Hvl0IGBJJAzJpN2mWtt+hWnFFA1EN4ENWAJiQ0i3NnA8KXLlKuNfzWH7qF4W91QAAAAASUVORK5CYII="
ICON_PNG_32 = "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAHNklEQVR4nLWXe4xU9RXHP+d3753ZmdkXs+zykLdbQwoIjY+Kj0RsDIothlJATEhMmzYNkJo+Yqm0jGujrUWiaVqLsU0DjRqgUqSYJtXEUiwaEKUgZaWlAcSFBRaWfczOvXPv7/SPO8vu7A4oJj3JyeT+5nfP+Z7v79zzOwcGi6os2qwO/yfJqRpUZfDawIOqIKIAi9t1pvYyv3CGL1C0GWsRMFfpzoKgJmEKVU0cTGR59cV62VtCYmgROwCg5HzRbk1FWZ7pevf9b13YvUN6j+zHBgUQA6pX518E1GISKdJTplF3893Uz779paLDwzumyrl+EIKq5ED+BcnCHl47s/W5Ocd/+2MbFXqtSVQJIp/s7Eqiig18Na5rxi19xIxZtuaQN4W7/jSaszyGuIu2YFoWS7TggD57Zuvzc/799IogNWZcwknXGLW2FIwMsXkZNgSEIXtR3GoDKMdeyAW2GE4b/+3HNzLW3JOzNra8uEOnn//L4YMfPHxrZKqqDagMUK5oFJX7cRxgKDOl04yKg7xbxPHoZ1Fcj+BcWzj9mb+7TV++Ze6ma+SvBiA8y1cv7N5GVOhVMabMuRgHt7ahTMU4wCAWRACL2hCvrrSvJkti5DjE9Qbyx1rE9Tj3+kb123kAwAUIOrih98i7mERK+mlHDNbvIzVhKlOfeK0s1tbV99F3ohWTTMVRiiHs7WTSyl8x8ksLCLsDvLo0nXt3cvTpryPGjZlUi0mmTO/R/eKf7b5ejBMD0JC09QsMT7h+BurKyR7EgDgexc52xi5ZxZiFDxF2QdUYKHx8kuPPfx9sBM4ACyKCDXxs4KcQEwOIPV0u2xUNhyZdyZjrEnaeIXvHIiZ8M0fxYhFxDGFXH0d+upSgow03XYfa8hxCBCnVnE9XXUTKlTgRo56LZJpv4Nof/AYtxkdnEg5H1y0n/5/3cDP1w50Pkastb6W3DDYo4NY30bx6I04mg/VDvFqPEy+0cH7XFtzaRjQKP9nUlf6Mz3roIhBZsJbmR35PauIkwi4fL5vg9KsvcmrLL/DqGss/xyuIW2nRGIMihPkupD89tN+/EuU7mbT8WbK3zMY/65NsSNK5521OrP8uXk22BL48NlXFOA42Kl+vCKAvn0e8JPWz5hAEAX5oY4MGot48IxetYsS9D9LTEWHSSTpaWzncsoSo4CMRoLZitGEU4WIlOQhcOQBVHMdh8sQJkTdiFNkfbnHyW5+MrvEKapJpUQt4KSbc/yAahJAGtI+jf/wZE0bW4k4cX/HcRYQgCJg5c1ax9dAB89+O7oSIKQcgIkRRRKa62u597/12gCW7gtEb1j95rgGKXKq9/ejdgd9XNlSMuIIowMpVubEH8z1iHFPOgBiD7/vSsuYntd6IUYRfXCm/3ri9esptc611kxigzw859lEPFAuogBiP9OGtOF1tqFtVkf4BBmaGhw7807z11i5pun2lqtUBAKqKMQa/UJC169ZVm6oaJs8/zTutezOfGzsP8WIK1A/Z9YdXiBrvgCgPXgZOuGR2PBVvkCH3xCD7qXSaIN9D7fjrGGtcVLVyEmYbGgE4tenn1E2bTX2VC0occTpB86H1fNTcgz/ja5ieM9gZczHuWrJvrsEmaksslIMQESJrSXmO9RIJoyWmKtaBKAqJrMWtbcBiiBQiwCpEaiiaJLVvPo7z8T6KyXps92m6r7ufCzMfQnvPxvujqEzDMERViaKorJ+4YiGKM7oCncZDooDsG4/i9JxCE9VI33m6blpBvvkeTOECmIrkDpNPV4pVy1Q0Qr0Ubncb2TceRWwIxoGwwIU71xA0fh7xu0r58GkAqJXLN52CuOUKAjbCJutItu2jfucTaCIDKJqooePup4gyTUhU6YqPA9JSe24AxDFB3FwMBSGojQi7LpZpfMMJ2BCbGkHmw+3U7HkOYyOcrpPY9Eg6b/0eKmbYCaoqJlGFuMk+1MZfQSLLwfS118/rePvP6lbXo5EttdQJgjPH+eA7s8uM2L5uTCIRZ7uCTdZSu38DmdbtJS8W3CQ4SbADNUziLsumJ0+TZGPNEbVRzEBVE1vqbpqHuN4QvvoZ6CjTSwwMjsx4mEJnrH4XTm97mfP4wB206NNw5wNS1cgmALNoszovNcq+mlk3bhq/9EdO4dSJQFwvvopFQAziJcoUMcObFCFuvUqqTvLSPjEO4noUTh8rjp6/3K27+a5/bJrA9pyqcbccQnOq5kgbK8csWz3dFvumnXx5bSiui0mmjIjE53i180npHVXF+gXVoq9jF6zwJq74ZVtyNMsAeGzIaPaVAzrKUX538Z2/3Xf29ZfJHz2ILfqlMesqAQigivGqSE+aSsOchdTfNm+nKN/YdqMczamaFhF7Ka5cTk1LaWBc0qb3BudY6Ld3z7BFP439jPOZqJpEMp8cU/OhN5Ktm0fLNoin5BaRCk2Dqgwbn10PcT6jut4wF7mclhW//wFCy2GyPLyMaQAAAABJRU5ErkJggg=="



def config_path():
    # Config dans %APPDATA%\Kali (standard pour un logiciel installé,
    # car Program Files n'est pas modifiable sans droits admin)
    base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Kali")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "config.json")


def get_window_title(hwnd):
    n = GetWindowTextLengthW(hwnd)
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def get_process_exe(hwnd):
    """Retourne le nom de l'exécutable (ex: 'dofus.exe') de la fenêtre."""
    pid = wt.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        CloseHandle(h)


def get_window_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def enum_dofus_windows():
    """Retourne [(hwnd, nom_perso, titre_complet)] pour chaque fenêtre Dofus.

    Détection triple :
      1. classe de fenêtre 'UnityWndClass' (moteur Unity de Dofus 3)
      2. nom du processus contenant 'dofus'
      3. titre contenant 'dofus' (secours)
    """
    results = []

    def cb(hwnd, lparam):
        if not IsWindowVisible(hwnd):
            return True
        title = get_window_title(hwnd)
        if not title:
            return True
        if title == APP_TITLE:  # notre propre fenêtre
            return True
        wclass = get_window_class(hwnd)
        exe = get_process_exe(hwnd)
        # Détection stricte : le PROCESSUS doit être Dofus. Le titre seul ne
        # suffit plus (un onglet de navigateur "dofus - Recherche" passait !).
        # La classe Unity ne sert de secours que si le processus est illisible
        # (jeu lancé en administrateur).
        is_dofus = (
            "dofus" in exe
            or (exe == "" and wclass == "UnityWndClass")
        )
        if not is_dofus:
            return True
        # ignore le launcher Ankama
        if "ankama" in exe:
            return True
        # Nom du perso : partie avant " - " si présente, sinon titre entier
        name = title.split(" - ")[0].strip()
        if not name or name.lower().startswith("dofus"):
            name = title
        results.append((hwnd, name, title))
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return results


def focus_window(hwnd):
    """Donne le focus à une fenêtre, même depuis une autre appli plein écran."""
    try:
        if IsIconic(hwnd):
            ShowWindow(hwnd, SW_RESTORE)
        fg = GetForegroundWindow()
        cur_tid = kernel32.GetCurrentThreadId()
        fg_tid = GetWindowThreadProcessId(fg, None)
        target_tid = GetWindowThreadProcessId(hwnd, None)
        AttachThreadInput(cur_tid, fg_tid, True)
        AttachThreadInput(cur_tid, target_tid, True)
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
        AttachThreadInput(cur_tid, fg_tid, False)
        AttachThreadInput(cur_tid, target_tid, False)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Thread des raccourcis clavier globaux
# ----------------------------------------------------------------------------
class HotkeyThread(threading.Thread):
    """Enregistre les hotkeys globaux et appelle un callback(id)."""

    def __init__(self, callback):
        super().__init__(daemon=True)
        self.callback = callback
        self.thread_id = None
        self._bindings = {}          # id -> (modifiers, vk)
        self._pending = None
        self._lock = threading.Lock()

    def set_bindings(self, bindings):
        """bindings : dict {hotkey_id: (modifiers, vk_code)}. Appliqué au prochain cycle."""
        with self._lock:
            self._pending = dict(bindings)
        if self.thread_id:
            PostThreadMessageW(self.thread_id, 0x0400, 0, 0)  # réveille la boucle

    def run(self):
        self.thread_id = kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        while True:
            with self._lock:
                if self._pending is not None:
                    for hid in self._bindings:
                        UnregisterHotKey(None, hid)
                    self._bindings = {}
                    for hid, (mods, vk) in self._pending.items():
                        if vk and RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                            self._bindings[hid] = (mods, vk)
                    self._pending = None
            if GetMessageW(ctypes.byref(msg), None, 0, 0) == 0:
                break
            if msg.message == WM_HOTKEY:
                self.callback(msg.wParam)


# ----------------------------------------------------------------------------
# Zone de notification (systray) — 100% API Windows native, aucune dépendance
# ----------------------------------------------------------------------------
shell32 = ctypes.windll.shell32

class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
        ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON), ("szTip", ctypes.c_wchar * 128),
        # champs pour les notifications Windows (bulles)
        ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD),
        ("szInfo", ctypes.c_wchar * 256), ("uTimeout", wt.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", wt.DWORD),
    ]


class TrayThread(threading.Thread):
    """Icône dans la zone des icônes cachées. Clic gauche = restaurer,
    clic droit = menu Ouvrir/Quitter."""
    WM_TRAY  = 0x8000 + 1
    MSG_SHOW = 0x8000 + 2
    MSG_HIDE = 0x8000 + 3
    MSG_NOTIFY = 0x8000 + 4

    def __init__(self, on_restore, on_quit):
        super().__init__(daemon=True)
        self.on_restore = on_restore
        self.on_quit = on_quit
        self.hwnd = None
        self._ready = threading.Event()
        self._visible = False
        self._notif = None
        self._notif_lock = threading.Lock()

    def notify(self, title, message):
        """Affiche une notification Windows depuis l'icône de zone de notif."""
        with self._notif_lock:
            self._notif = (title[:63], message[:255])
        self._ready.wait(2)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, self.MSG_NOTIFY, 0, 0)

    def _do_notify(self):
        with self._notif_lock:
            if not self._notif:
                return
            title, message = self._notif
            self._notif = None
        self._add()  # s'assure que l'icône existe
        self.nid.uFlags = 0x1 | 0x2 | 0x4 | 0x10  # + NIF_INFO
        self.nid.szInfoTitle = title
        self.nid.szInfo = message
        self.nid.dwInfoFlags = 0x1  # NIIF_INFO
        shell32.Shell_NotifyIconW(1, ctypes.byref(self.nid))  # NIM_MODIFY
        self.nid.uFlags = 0x1 | 0x2 | 0x4  # retire NIF_INFO pour la suite

    def show(self):
        self._ready.wait(2)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, self.MSG_SHOW, 0, 0)

    def hide(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, self.MSG_HIDE, 0, 0)

    # --- interne ---
    def _load_icon(self):
        # 1) .ico du dossier de mises à jour (permet de changer d'icône
        #    sans recompiler : il suffit d'y déposer un nouveau .ico)
        upd = os.path.join(os.path.dirname(config_path()), "kali.ico")
        if os.path.exists(upd):
            h = user32.LoadImageW(None, upd, 1, 0, 0, 0x10 | 0x40)
            if h:
                return h
        # 2) exe compilé : récupère l'icône embarquée dans l'exe lui-même
        if getattr(sys, "frozen", False):
            h = shell32.ExtractIconW(kernel32.GetModuleHandleW(None),
                                     sys.executable, 0)
            if h and h > 1:
                return h
        # script : charge le .ico s'il est à côté
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "kali.ico")
        if os.path.exists(ico):
            h = user32.LoadImageW(None, ico, 1, 0, 0, 0x10 | 0x40)
            if h:
                return h
        return user32.LoadIconW(None, 32512)  # icône Windows par défaut

    def _add(self):
        if self._visible:
            return
        self.nid = NOTIFYICONDATA()
        self.nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        self.nid.hWnd = self.hwnd
        self.nid.uID = 1
        self.nid.uFlags = 0x1 | 0x2 | 0x4  # MESSAGE | ICON | TIP
        self.nid.uCallbackMessage = self.WM_TRAY
        self.nid.hIcon = self._load_icon()
        self.nid.szTip = APP_TITLE
        shell32.Shell_NotifyIconW(0, ctypes.byref(self.nid))  # NIM_ADD
        self._visible = True

    def _remove(self):
        if self._visible:
            shell32.Shell_NotifyIconW(2, ctypes.byref(self.nid))  # NIM_DELETE
            self._visible = False

    def _popup_menu(self):
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, 0, 1, "Ouvrir " + APP_TITLE)
        user32.AppendMenuW(menu, 0x800, 0, None)  # séparateur
        user32.AppendMenuW(menu, 0, 2, "Quitter")
        user32.SetForegroundWindow(self.hwnd)
        user32.TrackPopupMenu.restype = ctypes.c_int
        cmd = user32.TrackPopupMenu(menu, 0x0100 | 0x0002,  # RETURNCMD | RIGHTBUTTON
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(menu)
        if cmd == 1:
            self.on_restore()
        elif cmd == 2:
            self._remove()
            self.on_quit()

    def run(self):
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT,
                                     wt.WPARAM, wt.LPARAM)
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]

        def wndproc(hwnd, msg, wp, lp):
            if msg == self.WM_TRAY:
                if lp == 0x0202:      # clic gauche relâché
                    self.on_restore()
                elif lp == 0x0205:    # clic droit relâché
                    self._popup_menu()
                return 0
            if msg == self.MSG_SHOW:
                self._add()
                return 0
            if msg == self.MSG_HIDE:
                self._remove()
                return 0
            if msg == self.MSG_NOTIFY:
                self._do_notify()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wp, lp)

        self._proc = WNDPROC(wndproc)  # garde une référence (sinon crash)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
            ]

        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = "KaliTrayWnd"
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, "KaliTrayWnd", "KaliTray",
                                           0, 0, 0, 0, 0, 0, 0, hinst, None)
        self._ready.set()

        msg = wt.MSG()
        while GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# ----------------------------------------------------------------------------
# Interface — thème Windows 11 sombre
# ----------------------------------------------------------------------------
C_BG        = "#202020"   # fond Mica sombre
C_CARD      = "#2b2b2b"   # cartes
C_CARD_HOV  = "#333333"
C_CARD_ACT  = "#0f3a5f"
C_STROKE    = "#3a3a3a"
C_TEXT      = "#ffffff"
C_TEXT_2    = "#9a9a9a"
C_ACCENT    = "#4cc2ff"   # accent Win11
C_ACCENT_D  = "#0078d4"
C_GREEN     = "#6ccb5f"


class App:
    HK_NEXT, HK_PREV = 1, 2
    HK_DIRECT_BASE = 10  # 10..17 = persos 1..8

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.configure(bg=C_BG)
        # ouverture centrée sur l'écran
        W, H = 330, 520
        x = (self.root.winfo_screenwidth() - W) // 2
        y = (self.root.winfo_screenheight() - H) // 2
        self.root.geometry(f"{W}x{H}+{x}+{y}")
        # barre de titre personnalisée (la barre blanche de Windows disparaît)
        self.root.overrideredirect(True)

        self.order = []            # noms de persos dans l'ordre d'initiative
        self.windows = {}          # nom -> hwnd
        self.current_index = -1
        self.cards = []
        self.drag = None
        self.anim_running = False
        self.session_start = None  # début de la session Dofus en cours
        self.minimized = False
        self.mb = None             # mini-barre flottante (mode réduit)
        self.mb_visible = False
        self._mb_hide_ticks = 0
        self.break_notified = 0    # heures de jeu déjà notifiées
        self.cfg = self.load_config()

        # zone de notification (natif Windows) — icône visible en permanence
        self.tray = TrayThread(
            on_restore=lambda: self.root.after(0, self.restore_from_tray),
            on_quit=lambda: self.root.after(0, self.on_close),
        )
        self.tray.start()
        # (icône de zone de notif affichée uniquement quand Kali est réduit)

        self.f_title = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.f_body  = tkfont.Font(family="Segoe UI", size=10)
        self.f_small = tkfont.Font(family="Segoe UI", size=9)

        self.build_ui()
        self.apply_win11_corners()

        self.hk = HotkeyThread(self.on_hotkey_raw)
        self.hk.start()
        self.apply_hotkeys()

        self.refresh_windows()
        self.tick()
        self.watch_foreground()

        # vérification des mises à jour GitHub (2 s après le démarrage,
        # en arrière-plan, silencieuse si pas d'internet)
        if self.cfg.get("auto_update", True):
            self.root.after(2000, self.check_updates_async)

        # clic sur l'icône de la barre des tâches (réduction) -> zone de notif
        self.root.bind("<Unmap>", self.on_unmap)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def apply_win11_corners(self):
        """Coins arrondis Windows 11 + présence dans la barre des tâches."""
        try:
            self.root.update_idletasks()
            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33,
                                                       ctypes.byref(pref), 4)
            # une fenêtre sans bordure disparaît de la barre des tâches ;
            # le style WS_EX_APPWINDOW l'y fait réapparaître
            GWL_EXSTYLE, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW = -20, 0x40000, 0x80
            get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            style = get_style(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            set_style(hwnd, GWL_EXSTYLE, style)
            # le style ne prend effet qu'après un cycle masquer/afficher,
            # MAIS seulement si Kali est censé être visible (pas en mini-barre)
            if not self.minimized:
                self.root.withdraw()
                self.root.after(10, self.root.deiconify)
        except Exception:
            pass

    def on_unmap(self, event):
        """Clic sur l'icône de la barre des tâches = réduction ->
        on redirige vers la zone de notification."""
        if event.widget is self.root and self.root.state() == "iconic":
            self.root.after(0, self.hide_to_tray)

    # ---------------- config ----------------
    def load_config(self):
        cfg = {"hk_next": "F1", "hk_prev": "F2", "topmost": True, "order": [],
               "notify_session": True, "direct_mod": "Alt", "auto_update": True, "break_reminder": True,
               "minibar": True, "auto_focus_first": True}
        try:
            with open(config_path(), "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
        return cfg

    def save_config(self):
        # répercute l'ordre affiché dans l'ordre maître : les comptes ouverts
        # prennent leurs nouvelles positions, les comptes fermés gardent la leur
        master = self.cfg.get("order", [])
        disp = iter(self.order)
        self.cfg["order"] = [next(disp) if n in self.windows else n
                             for n in master]
        try:
            with open(config_path(), "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------- UI ----------------
    def build_ui(self):
        # ---- Barre de titre personnalisée (style Win11 sombre) ----
        tbar = tk.Frame(self.root, bg=C_BG)
        tbar.pack(fill="x")

        # icônes unifiées : barre de titre + barre des tâches
        try:
            self._img16 = tk.PhotoImage(data=ICON_PNG_16)
            self._img20 = tk.PhotoImage(data=ICON_PNG_20)
            self._img32 = tk.PhotoImage(data=ICON_PNG_32)
            self.root.iconphoto(True, self._img32, self._img16)
            t_icon = tk.Label(tbar, image=self._img20, bg=C_BG)
        except Exception:
            t_icon = tk.Label(tbar, text="⚔", bg=C_BG, fg=C_ACCENT,
                              font=self.f_title)
        t_icon.pack(side="left", padx=(10, 4), pady=4)
        t_title = tk.Label(tbar, text=APP_TITLE, bg=C_BG, fg=C_TEXT,
                           font=self.f_title)
        t_title.pack(side="left")
        t_ver = tk.Label(tbar, text="v" + APP_VERSION, bg=C_BG, fg=C_TEXT_2,
                         font=self.f_small)
        t_ver.pack(side="left", padx=(5, 0), pady=(3, 0))

        # boutons fermer / réduire (réduire = zone de notification)
        btn_close = tk.Label(tbar, text="✕", bg=C_BG, fg=C_TEXT_2,
                             font=self.f_body, width=4, cursor="hand2")
        btn_close.pack(side="right", fill="y")
        btn_close.bind("<Button-1>", lambda e: self.on_close())
        btn_close.bind("<Enter>", lambda e: btn_close.configure(bg="#c42b1c", fg=C_TEXT))
        btn_close.bind("<Leave>", lambda e: btn_close.configure(bg=C_BG, fg=C_TEXT_2))

        btn_min = tk.Label(tbar, text="─", bg=C_BG, fg=C_TEXT_2,
                           font=self.f_body, width=4, cursor="hand2")
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Button-1>", lambda e: self.hide_to_tray())
        btn_min.bind("<Enter>", lambda e: btn_min.configure(bg=C_CARD_HOV, fg=C_TEXT))
        btn_min.bind("<Leave>", lambda e: btn_min.configure(bg=C_BG, fg=C_TEXT_2))

        # bouton options (engrenage)
        btn_opt = tk.Label(tbar, text="⚙", bg=C_BG, fg=C_TEXT_2,
                           font=("Segoe UI", 11), padx=10, cursor="hand2")
        btn_opt.pack(side="right", fill="y")
        btn_opt.bind("<Button-1>", self.show_options)
        btn_opt.bind("<Enter>", lambda e: btn_opt.configure(bg=C_CARD_HOV, fg=C_TEXT))
        btn_opt.bind("<Leave>", lambda e: btn_opt.configure(bg=C_BG, fg=C_TEXT_2))
        self.build_options_menu()

        # chrono de session (dans l'espace vide, ne change pas la mise en page)
        self.lbl_timer = tk.Label(tbar, text="", bg=C_BG, fg=C_TEXT_2,
                                  font=self.f_small)
        self.lbl_timer.pack(side="right", padx=(0, 8))
        self.update_timer()

        # déplacer la fenêtre en tirant la barre de titre
        for w in (tbar, t_icon, t_title, t_ver):
            w.bind("<ButtonPress-1>", self.title_press)
            w.bind("<B1-Motion>", self.title_drag)

        # ---- Ligne d'options : Actualiser + compteur ----
        bar = tk.Frame(self.root, bg=C_BG)
        bar.pack(fill="x", padx=10, pady=(4, 6))
        self.btn_refresh = self.make_button(bar, "⟳  Actualiser", self.refresh_windows)
        self.btn_refresh.pack(side="left")
        self.lbl_count = tk.Label(bar, text="", bg=C_BG, fg=C_TEXT_2,
                                  font=self.f_small)
        self.lbl_count.pack(side="right")

        # ---- Liste des persos ----
        self.list_frame = tk.Frame(self.root, bg=C_BG)
        self.list_frame.pack(fill="both", expand=True, padx=10)

        # ---- Raccourcis ----
        hkf = tk.Frame(self.root, bg=C_CARD, highlightbackground=C_STROKE,
                       highlightthickness=1)
        hkf.pack(fill="x", padx=10, pady=(6, 10))
        hkf.columnconfigure(1, weight=1)
        hkf.columnconfigure(3, weight=1)

        tk.Label(hkf, text="Raccourcis globaux", bg=C_CARD, fg=C_TEXT,
                 font=self.f_small).grid(row=0, column=0, columnspan=4,
                                         sticky="w", padx=8, pady=(6, 1))

        tk.Label(hkf, text="Suivant", bg=C_CARD, fg=C_TEXT_2,
                 font=self.f_small).grid(row=1, column=0, sticky="w", padx=(8, 3))
        self.var_next = tk.StringVar(value=self.cfg.get("hk_next", "F1"))
        self.make_key_menu(hkf, self.var_next).grid(row=1, column=1, sticky="w")

        tk.Label(hkf, text="Précédent", bg=C_CARD, fg=C_TEXT_2,
                 font=self.f_small).grid(row=1, column=2, sticky="e", padx=(0, 3))
        self.var_prev = tk.StringVar(value=self.cfg.get("hk_prev", "F2"))
        self.make_key_menu(hkf, self.var_prev).grid(row=1, column=3, sticky="e",
                                                    padx=(0, 8))

        self.lbl_direct = tk.Label(hkf, text="",
                 bg=C_CARD, fg=C_TEXT_2, font=self.f_small)
        self.lbl_direct.grid(
            row=2, column=0, columnspan=4, sticky="w", padx=8, pady=(1, 6))

        # ---- Zone de redimensionnement invisible (coin bas-droit) ----
        # taille 10x10 : tient dans la marge sans chevaucher le panneau,
        # et passe derrière les autres éléments par sécurité
        grip = tk.Frame(self.root, bg=C_BG, width=10, height=10,
                        cursor="size_nw_se")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.lower()
        grip.bind("<ButtonPress-1>", self.grip_press)
        grip.bind("<B1-Motion>", self.grip_drag)

    # --- déplacement de la fenêtre ---
    def title_press(self, event):
        self._move = (event.x_root - self.root.winfo_x(),
                      event.y_root - self.root.winfo_y())

    def title_drag(self, event):
        self.root.geometry(f"+{event.x_root - self._move[0]}"
                           f"+{event.y_root - self._move[1]}")

    # --- redimensionnement ---
    def grip_press(self, event):
        self._size = (event.x_root, event.y_root,
                      self.root.winfo_width(), self.root.winfo_height())

    def grip_drag(self, event):
        x0, y0, w0, h0 = self._size
        w = max(300, w0 + (event.x_root - x0))
        h = max(400, h0 + (event.y_root - y0))
        self.root.geometry(f"{w}x{h}")

    def hide_to_tray(self):
        self.minimized = True
        self.root.withdraw()
        self.tray.show()          # icône de notif SEULEMENT en mode réduit
        # la mini-barre s'affichera via watch_foreground quand Dofus est
        # au premier plan (montrée tout de suite si c'est déjà le cas)
        try:
            if GetForegroundWindow() in self.windows.values():
                self.show_minibar()
        except Exception:
            pass

    # ---------------- mini-barre flottante (mode réduit) ----------------
    # Design "portraits flottants" : des jetons circulaires posés directement
    # sur l'écran (fond transparent, pas de capsule), anneau coloré par
    # classe, double anneau lumineux sur le perso actif.
    MB_R = 21        # rayon des jetons
    MB_GAP = 14      # espace entre jetons
    MB_H = 66        # hauteur du canevas (marge pour le halo)

    def _ensure_minibar(self):
        """Crée la fenêtre mini-barre une seule fois (réutilisée ensuite)."""
        if self.mb is not None:
            return
        mb = tk.Toplevel(self.root)
        mb.overrideredirect(True)
        # PAS de 'topmost' : la mini-barre se comporte comme une fenêtre
        # normale (recouvrable). watch_foreground la remonte au-dessus de
        # Dofus quand le jeu est actif.
        self._mb_trans = "#010203"
        try:
            mb.attributes("-transparentcolor", self._mb_trans)
        except Exception:
            self._mb_trans = C_BG
        self.mb_canvas = tk.Canvas(mb, bg=self._mb_trans, bd=0,
                                   highlightthickness=0, height=self.MB_H)
        self.mb_canvas.pack()
        self.mb = mb
        self.mb_visible = False
        mb.withdraw()
        self.fill_minibar()
        self._place_minibar()

    def _place_minibar(self):
        if self.mb is None:
            return
        self.mb.update_idletasks()
        w = self.mb_canvas.winfo_reqwidth()
        sw, sh = self.mb.winfo_screenwidth(), self.mb.winfo_screenheight()
        pos = self.cfg.get("minibar_pos")
        if pos and 0 <= pos[0] <= sw - 40 and 0 <= pos[1] <= sh - 40:
            x, y = pos
        else:
            x, y = sw - w - 16, sh - self.MB_H - 64
        self.mb.geometry(f"+{x}+{y}")

    def show_minibar(self):
        """Affiche la mini-barre (création à la volée si besoin). Instantané.
        Ne fait rien si elle est déjà visible (évite tout clignotement)."""
        if not self.cfg.get("minibar", True):
            return
        if getattr(self, "mb_visible", False) and self.mb is not None:
            return
        self._ensure_minibar()
        self.mb.deiconify()
        self.mb.lift()
        self.mb_visible = True

    def hide_minibar(self):
        """Masque la mini-barre sans la détruire (réaffichage instantané)."""
        if self.mb is not None and getattr(self, "mb_visible", False):
            try:
                self.mb.withdraw()
            except Exception:
                pass
            self.mb_visible = False

    def destroy_minibar(self):
        """Détruit réellement la mini-barre (à la restauration de Kali)."""
        if self.mb is not None:
            try:
                self.mb.destroy()
            except Exception:
                pass
            self.mb = None
            self.mb_visible = False

    def fill_minibar(self):
        if self.mb is None:
            return
        c = self.mb_canvas
        c.delete("all")
        self._mb_imgs = []   # libère les images du rendu précédent
        n = len(self.order)
        R, GAP = self.MB_R, self.MB_GAP
        HALO = 10            # marge pour que le halo ne soit jamais coupé
        cell = 2 * R + GAP
        w = HALO + max(1, n) * cell - GAP + HALO + 30  # +30 : bouton restaurer
        h = self.MB_H
        c.configure(width=w)
        cy = h // 2

        for i, name in enumerate(self.order):
            cx = HALO + R + i * cell
            cls = self.klass.get(name, "")
            glyph, color = CLASS_STYLE.get(cls, CLASS_DEFAULT)
            active = (i == self.current_index)
            tag = f"mb{i}"
            hwnd = self.windows.get(name)

            # jeton haute qualité (Pillow) : halo + anneau + icône, anti-aliasé
            token = make_token_pil(hwnd, R, color, active) if hwnd else None
            if token is not None:
                self._mb_imgs.append(token)
                c.create_image(cx, cy, image=token, tags=tag)
            else:
                # repli canvas si Pillow indisponible ou pas d'icône
                if active:
                    for k, wdt in ((7, 1), (5, 1), (3, 2)):
                        c.create_oval(cx - R - k, cy - R - k,
                                      cx + R + k, cy + R + k,
                                      outline=C_ACCENT, width=wdt, tags=tag)
                c.create_oval(cx - R, cy - R, cx + R, cy + R,
                              fill="#16161e", outline=color,
                              width=2, tags=tag)
                pico = window_icon_pil(hwnd, int((R - 3) * 2)) if hwnd else None
                if pico is not None:
                    tkimg = ImageTk.PhotoImage(pico)
                    self._mb_imgs.append(tkimg)
                    c.create_image(cx, cy, image=tkimg, tags=tag)
                else:
                    abbr = CLASS_ABBR.get(cls, "?")
                    c.create_text(cx, cy, text=abbr, fill=color,
                                  font=("Segoe UI", 8, "bold"), tags=tag)

            # badge numéro (petit disque en bas à droite du jeton)
            bx, by = cx + R - 5, cy + R - 5
            c.create_oval(bx - 7, by - 7, bx + 7, by + 7,
                          fill=C_ACCENT if active else "#2b2b2b",
                          outline="#16161e", tags=tag)
            c.create_text(bx, by, text=str(i + 1),
                          fill="#16161e" if active else C_TEXT_2,
                          font=("Segoe UI", 7, "bold"), tags=tag)

            # clic = focus / glisser = déplacer (seuil de 5 px)
            c.tag_bind(tag, "<ButtonPress-1>",
                       lambda e, i=i: self.mb_press(e, i))
            c.tag_bind(tag, "<Enter>", lambda e: c.configure(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.configure(cursor=""))

        # bouton restaurer : petit jeton discret en bout de ligne
        bx = w - 16
        c.create_oval(bx - 10, cy - 10, bx + 10, cy + 10, fill="#16161e",
                      outline=C_STROKE, tags="mbrestore")
        c.create_text(bx, cy, text="\u25a3", fill=C_TEXT_2,
                      font=("Segoe UI", 8), tags="mbrestore")
        c.tag_bind("mbrestore", "<ButtonPress-1>",
                   lambda e: self.mb_press(e, -1))
        c.tag_bind("mbrestore", "<Enter>",
                   lambda e: c.configure(cursor="hand2"))
        c.tag_bind("mbrestore", "<Leave>",
                   lambda e: c.configure(cursor=""))

        c.bind("<B1-Motion>", self.mb_drag)
        c.bind("<ButtonRelease-1>", self.mb_release)

    @staticmethod
    def _soft(hex_color):
        """Version atténuée d'une couleur (pour adoucir le bord de l'anneau)."""
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        f = 0.55
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"

    def mb_press(self, event, index):
        self._mb_drag = {
            "dx": event.x_root - self.mb.winfo_x(),
            "dy": event.y_root - self.mb.winfo_y(),
            "x0": event.x_root, "y0": event.y_root,
            "index": index, "moved": False,
        }

    def mb_drag(self, event):
        d = getattr(self, "_mb_drag", None)
        if not d:
            return
        if not d["moved"]:
            if (abs(event.x_root - d["x0"]) < 5
                    and abs(event.y_root - d["y0"]) < 5):
                return
            d["moved"] = True
        self.mb.geometry(f"+{event.x_root - d['dx']}+{event.y_root - d['dy']}")

    def mb_release(self, event):
        d = getattr(self, "_mb_drag", None)
        self._mb_drag = None
        if not d:
            return
        if d["moved"]:
            self.cfg["minibar_pos"] = [self.mb.winfo_x(), self.mb.winfo_y()]
            self.save_config()
        elif d["index"] == -1:
            self.restore_from_tray()
        elif d["index"] >= 0:
            self.go_to(d["index"])

    def make_button(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=C_CARD, fg=C_TEXT, font=self.f_small,
                     padx=10, pady=4, cursor="hand2",
                     highlightbackground=C_STROKE, highlightthickness=1)
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg=C_CARD_HOV))
        b.bind("<Leave>", lambda e: b.configure(bg=C_CARD))
        return b

    def make_key_menu(self, parent, var):
        m = tk.OptionMenu(parent, var, *VK_CODES.keys(),
                          command=lambda _=None: self.on_hotkey_change())
        m.configure(bg=C_CARD_HOV, fg=C_TEXT, activebackground=C_ACCENT_D,
                    activeforeground=C_TEXT, bd=0, highlightthickness=0,
                    font=self.f_small, width=5, indicatoron=False, pady=2)
        m["menu"].configure(bg=C_CARD, fg=C_TEXT, activebackground=C_ACCENT_D,
                            font=self.f_small, bd=0)
        return m

    # ---------------- liste des persos ----------------
    def refresh_windows(self):
        wins = enum_dofus_windows()
        _TOKEN_CACHE.clear()   # icônes/jetons potentiellement obsolètes
        # noms uniques : si deux fenêtres ont le même titre (ex: deux "Dofus"
        # pas encore connectés), on suffixe (2), (3)...
        self.windows = {}
        self.klass = getattr(self, "klass", {})
        for hwnd, name, title in wins:
            base, n, unique = name, 2, name
            while unique in self.windows:
                unique = f"{base} ({n})"
                n += 1
            self.windows[unique] = hwnd
            # classe depuis le titre : "Nom - Classe - version - Release"
            seg = title.split(" - ")
            if len(seg) >= 2:
                self.klass[unique] = normalize_class(seg[1])

        # ORDRE MAÎTRE persistant : mémorise la position de TOUS les comptes
        # déjà vus, même fermés — les nouveaux sont ajoutés à la fin.
        master = self.cfg.get("order", [])
        for n in self.windows:
            if n not in master:
                master.append(n)
        self.cfg["order"] = master

        # ordre affiché = ordre maître filtré sur les fenêtres ouvertes
        self.order = [n for n in master if n in self.windows]

        # --- suivi de session : notification quand tout est fermé ---
        n_open = len(self.windows)
        if n_open > 0 and self.session_start is None:
            self.session_start = time.time()
            # focus automatique du perso n°1 de l'ordre d'initiative
            # (léger délai : laisse la fenêtre du jeu finir de s'afficher)
            if self.cfg.get("auto_focus_first", True) and self.order:
                self.root.after(800, lambda: self.go_to(0)
                                if self.order and self.session_start else None)
        elif n_open == 0 and self.session_start is not None:
            elapsed = time.time() - self.session_start
            self.session_start = None
            self.notify_session_end(elapsed)

        self.render_list()
        self.save_config()

    def update_timer(self):
        """Met à jour le chrono de session dans la barre de titre (1x/s)."""
        if self.session_start is not None:
            e = int(time.time() - self.session_start)
            h, m, s = e // 3600, (e % 3600) // 60, e % 60
            if h:
                txt = f"⏱ {h}:{m:02d}:{s:02d}"
            else:
                txt = f"⏱ {m}:{s:02d}"
            self.lbl_timer.config(text=txt)
            # rappel de pause : notification à chaque heure pleine de jeu
            if (self.cfg.get("break_reminder", True)
                    and e // 3600 > self.break_notified):
                self.break_notified = e // 3600
                hh = self.break_notified
                try:
                    self.notify_safe(
                        "Pense à faire une pause !",
                        f"Ça fait {hh} heure{'s' if hh > 1 else ''} que tu "
                        "joues. Bouge un peu, bois de l'eau — Dofus "
                        "t'attendra. 💧")
                except Exception:
                    pass
        else:
            self.lbl_timer.config(text="")
            self.break_notified = 0
        self.root.after(1000, self.update_timer)

    # ---------------- mise à jour automatique (GitHub) ----------------
    def check_updates_async(self, manual=False):
        threading.Thread(target=self._check_updates, args=(manual,),
                         daemon=True).start()

    def _check_updates(self, manual):
        try:
            data = None
            for url in UPDATE_URLS:
                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "Kali",
                                      "Cache-Control": "no-cache"})
                    data = urllib.request.urlopen(
                        req, timeout=10).read().decode("utf-8")
                    break
                except Exception:
                    continue
            if data is None:
                raise OSError("aucune adresse de mise à jour joignable")
            remote_v = parse_remote_version(data)
            if not remote_v:
                raise ValueError("version distante introuvable")
            if version_tuple(remote_v) > version_tuple(APP_VERSION):
                # sécurité : on vérifie que le fichier téléchargé est un
                # programme Python valide avant de l'installer
                compile(data, "app.py", "exec")
                path = os.path.join(os.path.dirname(config_path()), "app.py")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(data)
                self.root.after(0, self._update_done, remote_v)
            elif manual:
                self.root.after(0, lambda: messagebox.showinfo(
                    APP_TITLE, f"Tu es à jour (v{APP_VERSION})."))
        except Exception:
            if manual:
                self.root.after(0, lambda: messagebox.showinfo(
                    APP_TITLE,
                    "Impossible de vérifier les mises à jour.\n"
                    "Vérifie ta connexion internet."))

    def _update_done(self, new_version):
        messagebox.showinfo(
            APP_TITLE,
            f"Mise à jour v{new_version} installée !\n\n"
            "Kali va redémarrer pour l'appliquer.")
        self.restart_app()

    def restart_app(self):
        self.save_config()
        # retire l'icône de la zone de notification
        try:
            self.tray.hide()
        except Exception:
            pass
        # libère le verrou d'instance unique pour la nouvelle instance
        try:
            if MUTEX_HANDLE:
                kernel32.CloseHandle(MUTEX_HANDLE)
        except Exception:
            pass
        if getattr(sys, "frozen", False):
            # Relance DIFFÉRÉE (~1 s) : laisse l'ancienne instance nettoyer
            # son dossier temporaire _MEI avant que la nouvelle ne démarre
            # (sinon Windows affiche "Failed to remove temporary directory").
            env = os.environ.copy()
            for k in list(env):
                if k.startswith("_PYI") or k == "_MEIPASS2":
                    env.pop(k, None)
            CREATE_NO_WINDOW = 0x08000000
            # /d évite le souci de titre "" interprété comme chemin réseau ;
            # timeout laisse l'ancienne instance nettoyer son dossier _MEI
            subprocess.Popen(
                f'cmd /c timeout /t 1 /nobreak >nul & '
                f'start "Kali" /d "{os.path.dirname(sys.executable)}" '
                f'"{sys.executable}"',
                env=env, creationflags=CREATE_NO_WINDOW, shell=True)
        else:
            subprocess.Popen([sys.executable, sys.argv[0]])
        os._exit(0)

    # ---------------- menu options ----------------
    def build_options_menu(self):
        self.var_notify = tk.BooleanVar(
            value=self.cfg.get("notify_session", True)
            or self.cfg.get("break_reminder", True))
        m = tk.Menu(self.root, tearoff=0, bg=C_CARD, fg=C_TEXT,
                    activebackground=C_ACCENT_D, activeforeground=C_TEXT,
                    bd=0, font=self.f_small)
        m.add_checkbutton(label="Notifications (temps de jeu & pauses)",
                          variable=self.var_notify,
                          command=self.on_toggle_notify,
                          selectcolor=C_ACCENT)
        self.var_focus1 = tk.BooleanVar(
            value=self.cfg.get("auto_focus_first", True))
        m.add_checkbutton(label="Focus auto du perso n\u00b01",
                          variable=self.var_focus1,
                          command=self.on_toggle_focus1,
                          selectcolor=C_ACCENT)
        self.var_minibar = tk.BooleanVar(value=self.cfg.get("minibar", True))
        m.add_checkbutton(label="Mini-barre en mode réduit",
                          variable=self.var_minibar,
                          command=self.on_toggle_minibar,
                          selectcolor=C_ACCENT)
        # sous-menu : modificateur d'accès direct aux persos
        self.var_direct = tk.StringVar(value=self.cfg.get("direct_mod", "Alt"))
        sm = tk.Menu(m, tearoff=0, bg=C_CARD, fg=C_TEXT,
                     activebackground=C_ACCENT_D, activeforeground=C_TEXT,
                     bd=0, font=self.f_small)
        for mode in self.DIRECT_MODS:
            sm.add_radiobutton(label=mode, value=mode,
                               variable=self.var_direct,
                               command=lambda mo=mode: self.set_direct_mod(mo),
                               selectcolor=C_ACCENT)
        m.add_cascade(label="Accès direct aux persos", menu=sm)
        # mises à jour
        self.var_autoupd = tk.BooleanVar(value=self.cfg.get("auto_update", True))
        m.add_checkbutton(label="Mises à jour automatiques",
                          variable=self.var_autoupd,
                          command=self.on_toggle_autoupd,
                          selectcolor=C_ACCENT)
        m.add_command(label="Vérifier les mises à jour",
                      command=lambda: self.check_updates_async(manual=True))
        m.add_separator()
        m.add_command(label="Ouvrir le dossier des mises à jour",
                      command=self.open_update_folder)
        self.opt_menu = m

    def show_options(self, event):
        self.opt_menu.tk_popup(event.x_root, event.y_root)

    def on_toggle_notify(self):
        # une seule option pour les deux notifications de session
        state = self.var_notify.get()
        self.cfg["notify_session"] = state
        self.cfg["break_reminder"] = state
        self.save_config()

    def on_toggle_focus1(self):
        self.cfg["auto_focus_first"] = self.var_focus1.get()
        self.save_config()

    def on_toggle_minibar(self):
        self.cfg["minibar"] = self.var_minibar.get()
        self.save_config()
        if not self.cfg["minibar"]:
            self.destroy_minibar()
        elif self.minimized:
            self._mb_hide_ticks = 0

    def on_toggle_autoupd(self):
        self.cfg["auto_update"] = self.var_autoupd.get()
        self.save_config()

    def open_update_folder(self):
        try:
            os.startfile(os.path.dirname(config_path()))
        except Exception:
            pass

    def notify_safe(self, title, message):
        """Notification qui respecte le mode 'icône exclusive' : si Kali
        n'est pas réduit, l'icône apparaît le temps de la bulle puis repart."""
        self.tray.notify(title, message)
        if not self.minimized:
            self.root.after(12000, lambda: (self.tray.hide()
                                            if not self.minimized else None))

    def notify_session_end(self, elapsed):
        if not self.cfg.get("notify_session", True):
            return
        h, m = int(elapsed // 3600), int((elapsed % 3600) // 60)
        if h and m:
            dur = f"{h} h {m:02d} min"
        elif h:
            dur = f"{h} h"
        elif m:
            dur = f"{m} min"
        else:
            dur = "moins d'une minute"
        self.notify_safe("Session Dofus terminée",
                         f"Tu as joué pendant {dur}. À bientôt dans le Monde des Douze !")

    CARD_H = 34   # hauteur d'une carte
    CARD_GAP = 5  # espace entre cartes

    def slot_y(self, i):
        return i * (self.CARD_H + self.CARD_GAP)

    def render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.cards = []
        self.drag = None

        n = len(self.order)
        self.lbl_count.config(text=f"{n} fenêtre{'s' if n > 1 else ''} Dofus")
        if self.mb is not None and getattr(self, "mb_visible", False):
            self.fill_minibar()

        if not self.order:
            tk.Label(self.list_frame,
                     text="Aucune fenêtre Dofus détectée.\nLance tes comptes puis clique sur ⟳.",
                     bg=C_BG, fg=C_TEXT_2, font=self.f_body, justify="center"
                     ).pack(expand=True, pady=30)
            return

        self.canvas = tk.Canvas(self.list_frame, bg=C_BG, highlightthickness=0,
                                height=n * (self.CARD_H + self.CARD_GAP))
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        for i, name in enumerate(self.order):
            card = tk.Frame(self.canvas, bg=C_CARD,
                            highlightbackground=C_STROKE, highlightthickness=1)

            grip = tk.Label(card, text="⠿", bg=C_CARD, fg=C_TEXT_2,
                            font=self.f_small, cursor="fleur")
            grip.pack(side="left", padx=(8, 0))

            num = tk.Label(card, text="", width=2, bg=C_CARD, fg=C_TEXT_2,
                           font=self.f_body)
            num.pack(side="left", padx=(2, 2))

            lbl = tk.Label(card, text=name, bg=C_CARD, fg=C_TEXT,
                           font=self.f_body, anchor="w", cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True)

            # indicateur "fenêtre active" (visible seulement sur le perso courant)
            dot = tk.Label(card, text="", bg=C_CARD, fg=C_ACCENT,
                           font=self.f_small)
            dot.pack(side="right", padx=(0, 10))

            item = self.canvas.create_window(
                0, self.slot_y(i), window=card, anchor="nw",
                height=self.CARD_H, width=self.canvas.winfo_width() or 360)

            self.cards.append({"frame": card, "grip": grip, "num": num,
                               "lbl": lbl, "dot": dot, "item": item,
                               "y": float(self.slot_y(i))})

            for w in (card, grip, num, lbl, dot):
                w.bind("<ButtonPress-1>",   lambda e, c=card: self.drag_start(e, c))
                w.bind("<B1-Motion>",       self.drag_motion)
                w.bind("<ButtonRelease-1>", self.drag_end)
                w.bind("<Enter>", lambda e, c=card: self.set_hover(c, True))
                w.bind("<Leave>", lambda e, c=card: self.set_hover(c, False))

        self.update_all_cards()

    def on_canvas_resize(self, event):
        for c in self.cards:
            self.canvas.itemconfigure(c["item"], width=event.width)

    def index_of_card(self, frame):
        for i, c in enumerate(self.cards):
            if c["frame"] is frame:
                return i
        return -1

    # --- apparence des cartes ---
    def update_card(self, i):
        if i >= len(self.cards):
            return
        c = self.cards[i]
        dragging = self.drag and self.drag.get("moved") and self.drag["index"] == i
        active = (i == self.current_index)
        bg = C_CARD_ACT if (active or dragging) else C_CARD
        border = C_ACCENT if (active or dragging) else C_STROKE
        c["frame"].configure(bg=bg, highlightbackground=border)
        c["grip"].configure(bg=bg)
        c["num"].configure(bg=bg, text=str(i + 1),
                           fg=C_ACCENT if active else C_TEXT_2)
        c["lbl"].configure(bg=bg)
        c["dot"].configure(bg=bg,
                           text="\u25cf en jeu" if active else "")

    def update_all_cards(self):
        for i in range(len(self.cards)):
            self.update_card(i)
        # garde la mini-barre synchronisée (anneau bleu sur le bon perso)
        if self.mb is not None and getattr(self, "mb_visible", False):
            self.fill_minibar()

    def set_hover(self, frame, on):
        if self.drag and self.drag.get("moved"):
            return
        i = self.index_of_card(frame)
        if i == -1 or i == self.current_index:
            return
        c = self.cards[i]
        bg = C_CARD_HOV if on else C_CARD
        for k in ("frame", "grip", "num", "lbl", "dot"):
            c[k].configure(bg=bg)

    # --- animation : les cartes glissent vers leur emplacement ---
    def start_anim(self):
        if not self.anim_running:
            self.anim_running = True
            self.animate()

    def animate(self):
        moving = False
        for i, c in enumerate(self.cards):
            if self.drag and self.drag.get("moved") and self.drag["index"] == i:
                continue  # la carte tenue suit la souris, pas l'animation
            target = self.slot_y(i)
            dy = target - c["y"]
            if abs(dy) > 0.7:
                c["y"] += dy * 0.30  # interpolation douce (ease-out)
                moving = True
            else:
                c["y"] = float(target)
            self.canvas.coords(c["item"], 0, c["y"])
        if moving or (self.drag and self.drag.get("moved")):
            self.root.after(15, self.animate)  # ~60 fps
        else:
            self.anim_running = False

    # --- drag & drop ---
    def drag_start(self, event, frame):
        i = self.index_of_card(frame)
        if i == -1:
            return
        self.drag = {"index": i, "y0": event.y_root,
                     "card_y0": self.cards[i]["y"], "moved": False}

    def drag_motion(self, event):
        if not self.drag:
            return
        if not self.drag["moved"]:
            if abs(event.y_root - self.drag["y0"]) < 5:
                return  # petit mouvement = encore un simple clic
            self.drag["moved"] = True
            self.canvas.tag_raise(self.cards[self.drag["index"]]["item"])
            self.update_all_cards()
            self.start_anim()

        i = self.drag["index"]
        c = self.cards[i]
        # la carte tenue suit la souris
        new_y = self.drag["card_y0"] + (event.y_root - self.drag["y0"])
        max_y = self.slot_y(len(self.cards) - 1)
        c["y"] = max(0.0, min(float(max_y), new_y))
        self.canvas.coords(c["item"], 0, c["y"])

        # emplacement cible selon le centre de la carte tenue
        target = round((c["y"]) / (self.CARD_H + self.CARD_GAP))
        target = max(0, min(len(self.cards) - 1, target))

        if target != i:
            # réordonne : les autres cartes vont GLISSER vers leur place
            self.order.insert(target, self.order.pop(i))
            self.cards.insert(target, self.cards.pop(i))
            if self.current_index == i:
                self.current_index = target
            elif i < self.current_index <= target:
                self.current_index -= 1
            elif target <= self.current_index < i:
                self.current_index += 1
            self.drag["index"] = target
            self.update_all_cards()

    def drag_end(self, event):
        if not self.drag:
            return
        moved = self.drag["moved"]
        index = self.drag["index"]
        self.drag = None
        if moved:
            self.update_all_cards()
            self.start_anim()  # la carte lâchée glisse jusqu'à sa place
            self.save_config()
        else:
            self.go_to(index)  # simple clic = bascule sur la fenêtre

    # ---------------- navigation ----------------
    def go_to(self, index):
        if not self.order:
            return
        index %= len(self.order)
        name = self.order[index]
        hwnd = self.windows.get(name)
        if hwnd and IsWindow(hwnd):
            self.current_index = index
            focus_window(hwnd)
            self.update_all_cards()
        else:
            self.refresh_windows()

    def cycle(self, d):
        if not self.order:
            return
        self.go_to((self.current_index + d) % len(self.order))

    # ---------------- hotkeys ----------------
    # modificateurs d'accès direct : libellé -> code Windows
    DIRECT_MODS = {
        "Alt": 0x0001,
        "Ctrl": 0x0002,
        "Ctrl+Shift": 0x0006,
        "Désactivé": None,
    }

    def apply_hotkeys(self):
        bindings = {
            self.HK_NEXT: (0, VK_CODES.get(self.var_next.get())),
            self.HK_PREV: (0, VK_CODES.get(self.var_prev.get())),
        }
        # accès direct au perso n (0x31 = touche '1'), modificateur au choix
        # (Alt par défaut : Ctrl+1..8 = 2e barre de sorts dans Dofus !)
        mod = self.DIRECT_MODS.get(self.cfg.get("direct_mod", "Alt"))
        if mod is not None:
            for k in range(8):
                bindings[self.HK_DIRECT_BASE + k] = (mod, 0x31 + k)
        self.hk.set_bindings(bindings)
        self.update_direct_label()

    def update_direct_label(self):
        m = self.cfg.get("direct_mod", "Alt")
        txt = ("Accès direct : désactivé" if m == "Désactivé"
               else f"Accès direct : {m}+1 à {m}+8")
        if hasattr(self, "lbl_direct"):
            self.lbl_direct.config(text=txt)

    def set_direct_mod(self, mode):
        self.cfg["direct_mod"] = mode
        self.save_config()
        self.apply_hotkeys()

    def on_hotkey_change(self):
        if self.var_next.get() == self.var_prev.get():
            # évite les doublons : décale l'autre
            keys = list(VK_CODES.keys())
            i = keys.index(self.var_next.get())
            self.var_prev.set(keys[(i + 1) % len(keys)])
        self.cfg["hk_next"] = self.var_next.get()
        self.cfg["hk_prev"] = self.var_prev.get()
        self.save_config()
        self.apply_hotkeys()

    def on_hotkey_raw(self, hid):
        # appelé depuis le thread hotkey -> repasser dans le thread Tk
        self.root.after(0, self.on_hotkey, hid)

    def on_hotkey(self, hid):
        if hid == self.HK_NEXT:
            self.cycle(+1)
        elif hid == self.HK_PREV:
            self.cycle(-1)
        elif self.HK_DIRECT_BASE <= hid < self.HK_DIRECT_BASE + 8:
            self.go_to(hid - self.HK_DIRECT_BASE)

    # ---------------- zone de notification (systray) ----------------
    def restore_from_tray(self):
        self.minimized = False
        self._mb_hide_ticks = 0
        self.tray.hide()          # retour barre des tâches : icône retirée
        self.destroy_minibar()
        self.root.deiconify()
        self.root.lift()
        # impulsion "premier plan" pour passer devant, puis relâche
        # (la fenêtre n'est plus épinglée en permanence)
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        # réapplique coins arrondis + présence barre des tâches
        self.root.after(50, self.apply_win11_corners)

    # ---------------- boucle ----------------
    def tick(self):
        # rafraîchit automatiquement si une fenêtre a disparu/apparu
        wins = enum_dofus_windows()
        names = {name for _, name, _ in wins}
        if names != set(self.windows.keys()):
            self.refresh_windows()
        self.root.after(3000, self.tick)

    def watch_foreground(self):
        """Kali réduit : la mini-barre est TOUJOURS affichée mais se comporte
        comme une fenêtre normale (pas 'topmost'). Quand une fenêtre Dofus
        passe au premier plan, on replace la mini-barre juste au-dessus d'elle
        pour qu'elle reste visible ; sinon une autre appli la recouvre."""
        try:
            if self.minimized and self.cfg.get("minibar", True):
                self.show_minibar()          # garantit qu'elle existe/visible
                fg = GetForegroundWindow()
                on_dofus = fg in self.windows.values()
                # sur Dofus : placer la mini-barre juste AU-DESSUS de la
                # fenêtre Dofus active (et non au-dessus de tout)
                if on_dofus and self.mb is not None:
                    try:
                        mbid = int(self.mb.winfo_id())
                        SWP = 0x0010 | 0x0002 | 0x0001  # NOACTIVATE|NOMOVE|NOSIZE
                        user32.SetWindowPos(mbid, fg, 0, 0, 0, 0, SWP)
                    except Exception:
                        try:
                            self.mb.lift()
                        except Exception:
                            pass
        except Exception:
            pass
        self.root.after(200, self.watch_foreground)

    def on_close(self):
        try:
            self.tray.hide()
        except Exception:
            pass
        self.save_config()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


MUTEX_HANDLE = None


def already_running():
    """Verrou système : True si une instance de Kali tourne déjà."""
    global MUTEX_HANDLE
    kernel32.SetLastError(0)
    MUTEX_HANDLE = kernel32.CreateMutexW(None, False,
                                         "Kali_Instance_Unique")
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if already_running():
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showinfo(
            APP_TITLE,
            APP_TITLE + " est déjà lancé.\n\n"
            "Regarde dans la barre des tâches ou dans la zone de "
            "notification (icônes cachées, à côté de l'horloge).")
        _r.destroy()
    else:
        App().run()
