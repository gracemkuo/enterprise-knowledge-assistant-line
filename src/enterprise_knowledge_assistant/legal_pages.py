from html import escape


CONTACT_EMAIL = "eating1210kg@gmail.com"
EFFECTIVE_DATE = "2026-09-09"


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; color: #1f2937; background: #f8fafc; line-height: 1.7; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 48px 24px 72px; }}
    article {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 32px; box-shadow: 0 8px 30px rgba(15, 23, 42, .05); }}
    h1 {{ margin-top: 0; color: #111827; font-size: clamp(1.8rem, 5vw, 2.4rem); line-height: 1.25; }}
    h2 {{ margin-top: 2rem; color: #111827; font-size: 1.25rem; }}
    a {{ color: #0f766e; }}
    .meta {{ color: #64748b; }}
    footer {{ margin-top: 32px; color: #64748b; font-size: .9rem; text-align: center; }}
    @media (max-width: 560px) {{ main {{ padding: 20px 12px 40px; }} article {{ padding: 24px 20px; }} }}
  </style>
</head>
<body>
  <main>
    <article>
      {body}
    </article>
    <footer>Enterprise Knowledge Assistant</footer>
  </main>
</body>
</html>"""


def privacy_policy_html() -> str:
    return _page(
        "隱私權政策｜Enterprise Knowledge Assistant",
        f"""
<h1>隱私權政策</h1>
<p class="meta">生效日期：{EFFECTIVE_DATE}</p>
<p>本政策說明 Enterprise Knowledge Assistant（以下稱「本服務」）在您透過 LINE 或 WhatsApp 使用問答功能時，如何處理資訊。</p>

<h2>我們處理的資訊</h2>
<p>為了接收問題並將答案回覆到原通訊管道，本服務會處理您的 LINE 使用者識別碼或 WhatsApp 電話號碼識別資訊，以及您主動傳送的文字訊息。系統也可能產生雲端平台提供的必要技術與操作紀錄，例如請求時間、處理結果及錯誤資訊。</p>

<h2>資訊用途</h2>
<p>訊息文字會用於查詢 Google Agent Search，並根據已設定的私人知識來源產生答案，再透過 LINE 或 WhatsApp 回覆。識別資訊則用於確認您是否在允許名單中，以及將回覆送至正確的對話。</p>

<h2>儲存與分享</h2>
<p>本服務目前沒有另建應用程式資料庫來保存使用者訊息，也不會在應用程式日誌中主動記錄訊息正文或檢索出的文件內容。Google Cloud、LINE 與 Meta／WhatsApp 仍可能依各自的設定與政策處理傳輸資料及必要的操作紀錄。</p>
<p>本服務不出售個人資訊。僅在提供服務所必要的範圍內，由 Google Cloud、LINE 與 Meta／WhatsApp 等服務供應商處理相關資料，或於依法必須時提供。</p>

<h2>安全與存取限制</h2>
<p>本服務使用 webhook 簽章驗證、明確的使用者／電話白名單及雲端祕密管理機制限制存取。知識來源存放於私人雲端環境，並由 Google Agent Search 索引與查詢。</p>

<h2>您的選擇與資料刪除</h2>
<p>您可停止向本服務傳送訊息，或要求查詢、移除與您相關且由本服務控制的資料。操作方式請參閱<a href="/data-deletion">資料刪除說明</a>。</p>

<h2>政策更新</h2>
<p>本政策可能因服務功能或法規要求調整。更新版本會公布於本頁，並標示新的生效日期。</p>

<h2>聯絡方式</h2>
<p>如有隱私權或資料處理問題，請寄信至 <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>。</p>
""",
    )


def data_deletion_html() -> str:
    return _page(
        "資料刪除說明｜Enterprise Knowledge Assistant",
        f"""
<h1>使用者資料刪除說明</h1>
<p class="meta">更新日期：{EFFECTIVE_DATE}</p>
<p>如需要求刪除與您使用 Enterprise Knowledge Assistant 有關、且由本服務控制的資料，請依下列方式提出申請。</p>

<h2>申請方式</h2>
<p>請使用與您的 LINE 或 WhatsApp 帳號可合理核對的聯絡方式，寄信至 <a href="mailto:{CONTACT_EMAIL}?subject=Enterprise%20Knowledge%20Assistant%20資料刪除申請">{CONTACT_EMAIL}</a>，主旨請註明「Enterprise Knowledge Assistant 資料刪除申請」。</p>
<p>信件中請說明您使用的通訊管道（LINE 或 WhatsApp），以及足以辨識申請範圍的資訊。請不要在信中提供密碼、存取權杖、驗證碼或其他不必要的敏感資訊。</p>

<h2>處理方式</h2>
<p>收到申請後，我們會先核對申請人與範圍，再刪除或去識別化由本服務控制且能合理識別的相關資料。如特定資料依法必須保留，或僅存在於 LINE、Meta／WhatsApp 或 Google Cloud 等第三方服務中，我們會說明適用情況及可採取的後續方式。</p>

<h2>目前的資料保存方式</h2>
<p>本服務目前沒有另建應用程式資料庫保存訊息內容，也不會在應用程式日誌中主動記錄訊息正文或檢索出的文件內容。雲端平台及通訊服務仍可能依各自的政策與設定保存必要的操作紀錄。</p>

<p><a href="/privacy">返回隱私權政策</a></p>
""",
    )
