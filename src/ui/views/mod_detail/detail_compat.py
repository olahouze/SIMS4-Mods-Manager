"""
ModDetailCompatMixin: Provides property aliases for ModDetailView to maintain
strict backwards compatibility with legacy callers and unit tests.
"""


class ModDetailCompatMixin:
    """Mixin delegating property accesses to internal ModDetail sub-widgets."""

    @property
    def back_btn(self):
        """Exécute l'opération back btn.

        Returns:
            Résultat de l'opération back_btn.
        """
        return self.header_widget.back_btn

    @property
    def install_btn(self):
        """Exécute l'opération install btn.

        Returns:
            Résultat de l'opération install_btn.
        """
        return self.header_widget.install_btn

    @property
    def open_folder_btn(self):
        """Exécute l'opération open folder btn.

        Returns:
            Résultat de l'opération open_folder_btn.
        """
        return self.header_widget.open_folder_btn

    @property
    def web_btn(self):
        """Exécute l'opération web btn.

        Returns:
            Résultat de l'opération web_btn.
        """
        return self.header_widget.web_btn

    @property
    def title_lbl(self):
        """Exécute l'opération title lbl.

        Returns:
            Résultat de l'opération title_lbl.
        """
        return self.header_widget.title_lbl

    @property
    def thumb_label(self):
        """Exécute l'opération thumb label.

        Returns:
            Résultat de l'opération thumb_label.
        """
        return self.header_widget.thumb_label

    @property
    def meta_author(self):
        """Exécute l'opération meta author.

        Returns:
            Résultat de l'opération meta_author.
        """
        return self.header_widget.meta_author

    @property
    def meta_date(self):
        """Exécute l'opération meta date.

        Returns:
            Résultat de l'opération meta_date.
        """
        return self.header_widget.meta_date

    @property
    def meta_tags(self):
        """Exécute l'opération meta tags.

        Returns:
            Résultat de l'opération meta_tags.
        """
        return self.header_widget.meta_tags

    @property
    def installed_badge(self):
        """Exécute l'opération installed badge.

        Returns:
            Résultat de l'opération installed_badge.
        """
        return self.header_widget.installed_badge

    @property
    def source_badge(self):
        """Exécute l'opération source badge.

        Returns:
            Résultat de l'opération source_badge.
        """
        return self.header_widget.source_badge

    @property
    def req_frame(self):
        """Exécute l'opération req frame.

        Returns:
            Résultat de l'opération req_frame.
        """
        return self.requirements_widget.req_frame

    @property
    def req_body(self):
        """Exécute l'opération req body.

        Returns:
            Résultat de l'opération req_body.
        """
        return self.requirements_widget.req_body

    @property
    def req_title(self):
        """Exécute l'opération req title.

        Returns:
            Résultat de l'opération req_title.
        """
        return self.requirements_widget.req_title

    @property
    def req_desc(self):
        """Exécute l'opération req desc.

        Returns:
            Résultat de l'opération req_desc.
        """
        return self.requirements_widget.req_desc

    @property
    def req_collapse_btn(self):
        """Exécute l'opération req collapse btn.

        Returns:
            Résultat de l'opération req_collapse_btn.
        """
        return self.requirements_widget.req_collapse_btn

    @property
    def deps_layout(self):
        """Exécute l'opération deps layout.

        Returns:
            Résultat de l'opération deps_layout.
        """
        return self.requirements_widget.deps_layout

    @property
    def btn_report_author(self):
        """Exécute l'opération btn report author.

        Returns:
            Résultat de l'opération btn_report_author.
        """
        return self.requirements_widget.btn_report_author

    @property
    def _unfound_dep_names(self):
        return self.requirements_widget._unfound_dep_names

    @property
    def _comment_deps(self):
        return self.requirements_widget._comment_deps

    @property
    def gallery_frame(self):
        """Exécute l'opération gallery frame.

        Returns:
            Résultat de l'opération gallery_frame.
        """
        return self.gallery_widget.gallery_frame

    @property
    def gallery_title(self):
        """Exécute l'opération gallery title.

        Returns:
            Résultat de l'opération gallery_title.
        """
        return self.gallery_widget.gallery_title

    @property
    def gallery_cards_layout(self):
        """Exécute l'opération gallery cards layout.

        Returns:
            Résultat de l'opération gallery_cards_layout.
        """
        return self.gallery_widget.gallery_cards_layout

    @property
    def desc_browser(self):
        """Exécute l'opération desc browser.

        Returns:
            Résultat de l'opération desc_browser.
        """
        return self.desc_widget.desc_browser

    @property
    def is_installed(self) -> bool:
        """Exécute l'opération is installed.

        Returns:
            Résultat de l'opération is_installed.
        """
        return self.header_widget.is_installed

    @property
    def has_update(self) -> bool:
        """Exécute l'opération has update.

        Returns:
            Résultat de l'opération has_update.
        """
        return self.header_widget.has_update
