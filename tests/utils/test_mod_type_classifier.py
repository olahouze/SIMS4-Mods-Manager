from src.utils.mod_type_classifier import ModTypeClassifier
from src.database.models import CatalogMod
from src.database.manager import DatabaseManager


def test_mod_type_classifier_choices():
    choices = ModTypeClassifier.get_type_choices()
    assert len(choices) >= 9
    type_ids = [c[0] for c in choices]
    assert "all" in type_ids
    assert "animation" in type_ids
    assert "clothing" in type_ids
    assert "hair" in type_ids
    assert "body_skin" in type_ids
    assert "accessories_makeup" in type_ids
    assert "gameplay_script" in type_ids
    assert "objects_lots" in type_ids


def test_mod_type_classifier_sql_filter(tmp_path):
    db_file = tmp_path / "test_types.db"
    db_mgr = DatabaseManager(str(db_file))

    with db_mgr.get_session() as session:
        m_anim = CatalogMod(
            source="loverslab",
            remote_id="101",
            title="Passionate Animation Pack",
            category="Animations - WickedWhims",
            page_url="https://loverslab.com/101",
        )
        m_cloth = CatalogMod(
            source="loverslab",
            remote_id="102",
            title="Summer Dress 2024",
            category="Clothing",
            page_url="https://loverslab.com/102",
        )
        m_patreon_hair = CatalogMod(
            source="patreon",
            remote_id="103",
            title="Claire Hairstyle [Patreon]",
            category="The Sims 4",
            page_url="https://patreon.com/103",
        )
        m_patreon_hair.set_tags_list(["hair", "ts4cc", "female"])

        session.add_all([m_anim, m_cloth, m_patreon_hair])
        session.commit()

        # 1. Filter 'all' -> no restriction
        assert ModTypeClassifier.get_sql_filter("all", CatalogMod) is None

        # 2. Filter 'animation'
        f_anim = ModTypeClassifier.get_sql_filter("animation", CatalogMod)
        res_anim = session.query(CatalogMod).filter(f_anim).all()
        assert len(res_anim) == 1
        assert res_anim[0].remote_id == "101"

        # 3. Filter 'clothing'
        f_cloth = ModTypeClassifier.get_sql_filter("clothing", CatalogMod)
        res_cloth = session.query(CatalogMod).filter(f_cloth).all()
        assert len(res_cloth) == 1
        assert res_cloth[0].remote_id == "102"

        # 4. Filter 'hair'
        f_hair = ModTypeClassifier.get_sql_filter("hair", CatalogMod)
        res_hair = session.query(CatalogMod).filter(f_hair).all()
        assert len(res_hair) == 1
        assert res_hair[0].remote_id == "103"
