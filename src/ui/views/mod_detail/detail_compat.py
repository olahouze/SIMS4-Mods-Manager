"""
ModDetailCompatMixin: Provides property aliases for ModDetailView to maintain
strict backwards compatibility with legacy callers and unit tests.
"""


class ModDetailCompatMixin:
    """Mixin delegating property accesses to internal ModDetail sub-widgets."""

    @property
    def back_btn(self):
        return self.header_widget.back_btn

    @property
    def install_btn(self):
        return self.header_widget.install_btn

    @property
    def open_folder_btn(self):
        return self.header_widget.open_folder_btn

    @property
    def web_btn(self):
        return self.header_widget.web_btn

    @property
    def title_lbl(self):
        return self.header_widget.title_lbl

    @property
    def thumb_label(self):
        return self.header_widget.thumb_label

    @property
    def meta_author(self):
        return self.header_widget.meta_author

    @property
    def meta_date(self):
        return self.header_widget.meta_date

    @property
    def meta_tags(self):
        return self.header_widget.meta_tags

    @property
    def installed_badge(self):
        return self.header_widget.installed_badge

    @property
    def source_badge(self):
        return self.header_widget.source_badge

    @property
    def req_frame(self):
        return self.requirements_widget.req_frame

    @property
    def req_body(self):
        return self.requirements_widget.req_body

    @property
    def req_title(self):
        return self.requirements_widget.req_title

    @property
    def req_desc(self):
        return self.requirements_widget.req_desc

    @property
    def req_collapse_btn(self):
        return self.requirements_widget.req_collapse_btn

    @property
    def deps_layout(self):
        return self.requirements_widget.deps_layout

    @property
    def btn_report_author(self):
        return self.requirements_widget.btn_report_author

    @property
    def _unfound_dep_names(self):
        return self.requirements_widget._unfound_dep_names

    @property
    def _comment_deps(self):
        return self.requirements_widget._comment_deps

    @property
    def gallery_frame(self):
        return self.gallery_widget.gallery_frame

    @property
    def gallery_title(self):
        return self.gallery_widget.gallery_title

    @property
    def gallery_cards_layout(self):
        return self.gallery_widget.gallery_cards_layout

    @property
    def desc_browser(self):
        return self.desc_widget.desc_browser

    @property
    def is_installed(self) -> bool:
        return self.header_widget.is_installed

    @property
    def has_update(self) -> bool:
        return self.header_widget.has_update
