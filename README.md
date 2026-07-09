<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=30&duration=3000&pause=800&color=00D9FF&center=true&vCenter=true&width=680&lines=VelaVPN+Bot;Telegram-First+%E2%80%A2+3x--ui+Powered;Sell+%E2%80%A2+Provision+%E2%80%A2+Automate" alt="VelaVPN Bot" />

<br/>

<img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/aiogram-3.29-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" />
<img src="https://img.shields.io/badge/SQLite-WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />
<img src="https://img.shields.io/badge/3x--ui-panel-FF6B35?style=for-the-badge" />
<img src="https://img.shields.io/badge/license-MIT-22C55E?style=for-the-badge" />

<br/>

<img src="https://img.shields.io/github/last-commit/mhndev3/velavpn-bot?style=flat-square&color=00D9FF" />
<img src="https://img.shields.io/github/languages/code-size/mhndev3/velavpn-bot?style=flat-square&color=8B5CF6" />
<img src="https://img.shields.io/github/commit-activity/m/mhndev3/velavpn-bot?style=flat-square&color=F59E0B" />

<br/><br/>

<h3>A production-grade Persian Telegram bot for selling & provisioning VPN configs</h3>
<p><i>Fully automated: buy → pay → provision on 3x-ui → deliver QR + link</i></p>

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=120&section=footer" width="100%"/>

</div>

---

## ✨ Highlights

<table>
<tr>
<td width="50%" valign="top">

### 🛒 For Customers
- **Hierarchical buy flow** — location → duration → volume
- **Custom config naming** — pick your own service name
- **One-message delivery** — QR image + link + full details
- **Live usage stats** — remaining GB, % used, days left
- **Import existing configs** — paste any `vless/vmess/trojan/ss` link
- **Wallet, referrals, tickets, FAQ** built in

</td>
<td width="50%" valign="top">

### 👑 For Admins
- **Three-tier roles** — user / sub-admin / head-admin
- **Full UI customization** — every text, emoji, banner & button
- **Premium (animated) emoji** support in messages
- **Forced channel join** — add/remove channels live
- **Plan editor** — price, volume, duration, location
- **Death Note dev panel** — stop / start / lockdown the bot

</td>
</tr>
</table>

---

## 🧭 Onboarding Flow

```mermaid
flowchart LR
    A([/start]) --> B{Rules<br/>accepted?}
    B -- no --> B1[📜 Show rules] --> B
    B -- yes --> C{Joined<br/>channels?}
    C -- no --> C1[🔒 Join gate] --> C
    C -- yes --> D{Phone<br/>verified?}
    D -- no --> D1[📱 Share contact] --> D
    D -- yes --> E{Username<br/>set?}
    E -- no --> E1[👤 Ask username] --> E
    E -- yes --> F([🎉 Main menu])

    style A fill:#00D9FF,stroke:#0891b2,color:#000
    style F fill:#22C55E,stroke:#15803d,color:#000
```

## 🔄 Purchase → Provision Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant B as 🤖 Bot
    participant A as 👑 Admin
    participant X as 🖥 3x-ui Panel

    U->>B: Pick location → duration → volume
    U->>B: Choose config name
    U->>B: Upload payment receipt
    B->>A: Forward receipt for review
    A->>B: ✅ Approve
    B->>X: POST /panel/api/clients/add
    X-->>B: client created
    B->>X: GET /panel/api/hosts/list
    X-->>B: real serving domain
    B-->>U: 📸 QR + 🔗 link (single message)
```

---

## 🏗 Architecture

```
velavpn-bot/
├── main.py                      # Entry point · routers & middleware wiring
├── config/settings.py           # Env config + smart ADMIN_IDS (DB-aware)
│
├── handlers/                    # Telegram update handlers
│   ├── onboarding.py            #   rules → join → phone → username
│   ├── user_shop.py             #   hierarchical buy flow
│   ├── user_extra.py            #   my configs · referrals · partnership
│   ├── admin_payment_review.py  #   approve → provision → deliver
│   ├── head_admin_panel.py      #   servers · admins · channels · settings
│   ├── admin_ui_settings.py     #   texts / emojis / banners / colors
│   ├── glass_menu.py            #   inline ("glass") menu mode
│   └── dev_control.py           #   Death Note developer panel
│
├── services/
│   ├── xui_service.py           # 3x-ui client: login · provision · links · stats
│   ├── ui_render.py             # premium-emoji aware message rendering
│   ├── ui_texts.py              # T(key, default) editable-text reader
│   └── banner_service.py        # per-screen banners
│
├── database/
│   ├── db.py                    # connection pool · WAL · settings cache
│   ├── migration.py             # additive schema migrations
│   └── backup.py                # automated 24h backups
│
└── keyboards/                   # dynamic keyboards (renamable buttons)
```

### Design decisions worth knowing

| Concern | Approach |
|---|---|
| **Renamable buttons** | A custom `Btn` filter resolves the *live* setting value, so renaming a button from the admin panel never breaks its handler |
| **Role gating** | `ADMIN_IDS` is a smart object whose `__contains__` also queries the DB — every `x in ADMIN_IDS` check became DB-aware with zero call-site edits |
| **Concurrency** | SQLite connection pool (LIFO, max 8) + `WAL` + `busy_timeout` + periodic checkpoint |
| **Caching** | Settings table cached (5 s TTL); content pages cached (10 s TTL) |
| **Correct domain** | Read live from the panel's **Hosts** section — never a stale IP or `externalProxy` |
| **Premium emoji** | Persist message text **and** its `custom_emoji` entities, then replay them on send |

---

## 🚀 Quick Start

```bash
git clone https://github.com/mhndev3/velavpn-bot.git
cd velavpn-bot

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env            # then fill it in
python main.py
```

### Environment

```env
BOT_TOKEN=123456:ABC...              # from @BotFather
ADMIN_IDS=11111111,22222222          # static head-admins (comma separated)
DEVELOPER_ID=11111111                # unlocks /deathnote
ADMIN_REPORT_CHANNEL_ID=-100...      # order notifications

USE_PROXY=false                      # optional SOCKS/HTTP proxy
PROXY_TYPE=socks5
PROXY_HOST=127.0.0.1
PROXY_PORT=1080
```

> [!IMPORTANT]
> `.env`, `bot.db` and `backups/` are git-ignored on purpose. They hold your bot token, live customer data and admin-authored UI content. **Never** commit or overwrite them during a deploy.

---

## 📦 Deployment (pm2)

```bash
# copy code files ONLY — never .env / bot.db / backups / venv
cd ~/velavpn-bot
venv/bin/pip install -r requirements.txt
pm2 restart velavpn && pm2 logs velavpn
```

Schema migrations run automatically on boot, so a plain restart is enough.

---

## 🎛 Admin Panel Tour

| Section | What you can change |
|---|---|
| 🎨 **UI Settings** | Every user-facing text, emoji, banner and button label — live, no restart |
| 🖥 **Servers** | Add 3x-ui panels, test connections, list inbounds, override domain |
| 📦 **Plans** | Create & **edit** plans: price, volume, duration, location |
| 📢 **Channels** | Forced-join channels (add via `@username`, link, or forward) |
| 👑 **Head Admins** | Grant/revoke full panel access by numeric ID |
| ⚙️ **Bot Settings** | Card number, referral %, glass-button mode, DB download |
| 💀 **`/deathnote`** | Developer-only: `Stop` · `Start` · `L` (lockdown) · `K` (unlock) |

---

## 🗺 Roadmap

- [x] Hierarchical buy flow with custom config names
- [x] Domain auto-resolution from the panel's Hosts section
- [x] Premium (animated) emoji in bot messages
- [x] Forced channel join + full onboarding gate
- [x] Live usage stats & percentage bars
- [ ] **Telegram Mini App** — fully styled UI with real button colors
- [ ] Cross-platform client (Flutter + Xray-core)
- [ ] Advanced analytics dashboard

---

## 🤝 Contributing

Issues and pull requests are welcome. For substantial changes, please open an issue first to discuss what you'd like to change.

## 📄 License

Released under the [MIT License](LICENSE).

---

<div align="center">

**Built with care for real customers.**

<sub>Made by <a href="https://github.com/mhndev3">@mhndev3</a> · Powered by aiogram & 3x-ui</sub>

</div>
