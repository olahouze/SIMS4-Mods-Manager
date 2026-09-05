from src.database import DatabaseManager, CatalogMod, InstalledMod
from src.utils.mod_matcher import ModMatcher


def test_clean_mod_title_variations():
    # 1. Bracketed creator and version
    assert ModMatcher.clean_mod_title("[Scumbumbo] XML Injector v4.2 [Updated]") == "xml injector"

    # 2. Bracketed version, TS4 tag, and date
    assert ModMatcher.clean_mod_title("[V2.1] [TS4] WickedWhims - July 2024") == "wickedwhims"

    # 3. Creator suffix and multi-digit version
    assert ModMatcher.clean_mod_title("Basemental Drugs v7.18.150 - By Basemental") == "basemental drugs"

    # 4. Author possessive prefix
    assert ModMatcher.clean_mod_title("Scumbumbo's XML Injector") == "xml injector"

    # 5. Creator dash prefix
    assert ModMatcher.clean_mod_title("Kuttoe - Mini Mods") == "mini mods"

    # 6. Generic xxx with prefix and suffix
    assert ModMatcher.clean_mod_title("[AuthorName] xxx Mod v2.0 (2024-05)") == "xxx"


def test_mod_matcher_scores():
    # Exact core match after cleaning
    score_xml = ModMatcher.match_score("XML Injector", "[Scumbumbo] XML Injector v4.2 [Updated]")
    assert score_xml >= 0.90

    score_drugs = ModMatcher.match_score("Basemental Drugs", "Basemental Drugs v7.18.150 - By Basemental")
    assert score_drugs >= 0.90

    score_ww = ModMatcher.match_score("WickedWhims", "[TURBODRIVER] WickedWhims (v175e - 10 July 2024)")
    assert score_ww >= 0.90

    # xxx vs [Creator] xxx v1.0
    score_xxx = ModMatcher.match_score("xxx", "[MyCreator] xxx v1.0 [TS4]")
    assert score_xxx >= 0.90

    # Dissimilar titles should produce low scores
    score_unrelated = ModMatcher.match_score("XML Injector", "Better Exceptions Mod v3.1")
    assert score_unrelated < 0.40


def test_find_best_catalog_match(tmp_path):
    db_file = tmp_path / "test_matcher.db"
    db_mgr = DatabaseManager(str(db_file))

    with db_mgr.get_session() as session:
        cm1 = CatalogMod(
            source="loverslab",
            remote_id="501",
            title="[Scumbumbo] XML Injector v4.2 [Updated 2024]",
            author="Scumbumbo",
            page_url="https://loverslab.com/files/file/501-xml-injector/",
        )
        cm2 = CatalogMod(
            source="loverslab",
            remote_id="502",
            title="Basemental Drugs v7.18.150 - By Basemental",
            author="Basemental",
            page_url="https://loverslab.com/files/file/502-basemental-drugs/",
        )
        session.add_all([cm1, cm2])
        session.commit()

        # Query parent requirement 'XML Injector'
        match1 = ModMatcher.find_best_catalog_match("XML Injector", session, min_threshold=0.75)
        assert match1 is not None
        mod1, score1 = match1
        assert mod1.remote_id == "501"
        assert score1 >= 0.85

        # Query parent requirement 'Basemental Drugs'
        match2 = ModMatcher.find_best_catalog_match("Basemental Drugs", session, min_threshold=0.75)
        assert match2 is not None
        mod2, score2 = match2
        assert mod2.remote_id == "502"
        assert score2 >= 0.85

        # Query completely unrelated
        match_none = ModMatcher.find_best_catalog_match("Totally Unknown Mod XYZ", session, min_threshold=0.75)
        assert match_none is None


def test_find_best_installed_match():
    inst1 = InstalledMod(
        source="loverslab",
        remote_id="501",
        title="[Scumbumbo] XML Injector v4",
        folder_name="xml_injector",
    )
    inst2 = InstalledMod(
        source="loverslab",
        remote_id="502",
        title="WonderfulWhims - v52",
        folder_name="wonderfulwhims",
    )
    installed_list = [inst1, inst2]

    # Matching 'XML Injector' against installed
    m1 = ModMatcher.find_best_installed_match("XML Injector", installed_list, min_threshold=0.75)
    assert m1 is not None
    mod1, score1 = m1
    assert mod1.folder_name == "xml_injector"
    assert score1 >= 0.85

    # Matching 'WonderfulWhims'
    m2 = ModMatcher.find_best_installed_match("WonderfulWhims", installed_list, min_threshold=0.75)
    assert m2 is not None
    mod2, score2 = m2
    assert mod2.folder_name == "wonderfulwhims"
