# 字源故事

故事数据.js维护window.GLYPH_STORIES；故事展示.js通过StoryPanel.renderRecord(glyph,glyphs,onSelect)更新故事区域。

优先按完整字形ID登记headline/source/timeline。历史节点可有label/image/text/caption/source；取得并核对材料后才能添加。原有本义、引申义、构形来自字形记录，人工录入约定见docs/CONTRIBUTING.md。

IDS候选显示为“先验，待校核”，不能写成已证实的小篆构形。先从有资料的字做短故事，附出处、版本、复核人。本组可独立改文案与排版，保留接口和元素ID；字形通过GlyphUI.vectorMarkup调用，不复制几何。
