"""
Classifier and SQL filter generator for generic Sims 4 mod types across multiple source providers
(LoversLab, Patreon, etc.).
"""

from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy import or_


class ModTypeClassifier:
    """
    Standardized canonical taxonomy for Sims 4 mod types, mapping generic human-friendly
    categories to provider-specific categories, tags, and keywords.
    """

    TYPES_DEFINITIONS: Dict[str, Dict[str, Any]] = {
        "all": {
            "id": "all",
            "label": "Tous les types",
            "icon": "✨",
        },
        "animation": {
            "id": "animation",
            "label": "Animations & Poses",
            "icon": "🎬",
            "loverslab_categories": [
                "Animations - WickedWhims",
                "Animations - Other",
            ],
            "keywords": [
                "animation",
                "animations",
                "pose",
                "poses",
                "poselist",
                "anim",
                "motion",
            ],
        },
        "clothing": {
            "id": "clothing",
            "label": "Vêtements & Tenues",
            "icon": "👗",
            "loverslab_categories": [
                "Clothing",
            ],
            "keywords": [
                "clothing",
                "clothes",
                "dress",
                "dresses",
                "outfit",
                "outfits",
                "lingerie",
                "underwear",
                "shoes",
                "top",
                "bottom",
                "pants",
                "skirt",
                "shirt",
                "jacket",
                "swimsuit",
                "bikini",
                "costume",
                "robe",
                "vetement",
                "tenue",
            ],
        },
        "hair": {
            "id": "hair",
            "label": "Coiffures",
            "icon": "💇",
            "loverslab_categories": [
                "Hair",
            ],
            "keywords": [
                "hair",
                "hairstyle",
                "hairstyles",
                "hairs",
                "cheveux",
                "coiffure",
                "coiffures",
            ],
        },
        "body_skin": {
            "id": "body_skin",
            "label": "Peaux, Corps & Presets",
            "icon": "✨",
            "loverslab_categories": [
                "Body Parts",
            ],
            "keywords": [
                "body",
                "skin",
                "skinblend",
                "skinoverlay",
                "overlay",
                "preset",
                "presets",
                "slider",
                "sliders",
                "penis",
                "vagina",
                "boobs",
                "eyes",
                "teeth",
                "feet",
                "hands",
                "peau",
                "corps",
            ],
        },
        "accessories_makeup": {
            "id": "accessories_makeup",
            "label": "Accessoires & Maquillage",
            "icon": "💄",
            "loverslab_categories": [
                "Accessories & Makeup",
            ],
            "keywords": [
                "accessories",
                "accessory",
                "makeup",
                "make-up",
                "tattoo",
                "tattoos",
                "jewelry",
                "piercing",
                "glasses",
                "hat",
                "hats",
                "nails",
                "lipstick",
                "eyeshadow",
                "eyeliner",
                "blush",
                "accessoire",
                "maquillage",
            ],
        },
        "gameplay_script": {
            "id": "gameplay_script",
            "label": "Gameplay & Scripts",
            "icon": "⚙️",
            "loverslab_categories": [
                "WickedWhims",
                "Extensions",
            ],
            "keywords": [
                "script",
                "gameplay",
                "injector",
                "career",
                "trait",
                "system",
                "tuning",
                "interaction",
                "overhaul",
            ],
        },
        "objects_lots": {
            "id": "objects_lots",
            "label": "Objets, Meubles & Terrains",
            "icon": "🏠",
            "loverslab_categories": [
                "Objects",
                "Paintings & Posters",
                "Lots",
            ],
            "keywords": [
                "object",
                "objects",
                "furniture",
                "decor",
                "deco",
                "poster",
                "painting",
                "paintings",
                "lot",
                "lots",
                "house",
                "build",
                "room",
                "meuble",
                "terrain",
            ],
        },
        "translations": {
            "id": "translations",
            "label": "Traductions",
            "icon": "🌐",
            "loverslab_categories": [
                "Translations",
                "Translations - WickedWhims",
            ],
            "keywords": [
                "translation",
                "translations",
                "traduction",
                "traductions",
                "french",
                "francais",
                "spanish",
                "german",
                "chinese",
                "russian",
                "italian",
            ],
        },
        "other": {
            "id": "other",
            "label": "Autres",
            "icon": "📦",
            "loverslab_categories": [
                "Other",
                "Uncategorized",
            ],
            "keywords": [],
        },
    }

    @classmethod
    def get_type_choices(cls) -> List[Tuple[str, str]]:
        """Returns list of (type_id, display_label) tuples for UI comboboxes."""
        return [(t_id, f"{info['icon']} {info['label']}") for t_id, info in cls.TYPES_DEFINITIONS.items()]

    @classmethod
    def get_sql_filter(cls, mod_type: Optional[str], catalog_model):
        """
        Builds SQLAlchemy filter condition matching the requested generic mod type
        across LoversLab categories and tags, and Patreon tags and titles.
        """
        if not mod_type or mod_type.lower() in ["all", ""]:
            return None

        m_type = mod_type.lower()
        type_info = cls.TYPES_DEFINITIONS.get(m_type)
        if not type_info:
            return None

        conditions = []

        # 1. LoversLab Category matches
        ll_cats = type_info.get("loverslab_categories", [])
        if ll_cats:
            cat_filters = [catalog_model.category.ilike(f"%{cat}%") for cat in ll_cats]
            conditions.extend(cat_filters)

        # 2. Tag and title keyword matches (applies to Patreon and cross-site tags)
        keywords = type_info.get("keywords", [])
        for kw in keywords:
            conditions.append(catalog_model.tags.ilike(f"%{kw}%"))
            conditions.append(catalog_model.title.ilike(f"%{kw}%"))

        if not conditions:
            return None

        return or_(*conditions)
