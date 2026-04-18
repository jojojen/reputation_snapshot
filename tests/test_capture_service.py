from __future__ import annotations

from services.capture_service import extract_item_seller_context


def test_extract_item_seller_context_reads_profile_url_and_review_count() -> None:
    raw_html = """
    <section>
      <a href="/user/profile/492792377" data-location="item_details:seller_info"
         aria-label="山本商店, 961件のレビュー, 5段階評価中4.5, 本人確認済">
        山本商店
      </a>
    </section>
    """
    visible_text = "\n".join(["出品者", "山本商店", "961", "本人確認済"])

    context = extract_item_seller_context(raw_html, visible_text)

    assert context["profile_url"] == "https://jp.mercari.com/user/profile/492792377"
    assert context["display_name"] == "山本商店"
    assert context["seller_total_reviews"] == 961
