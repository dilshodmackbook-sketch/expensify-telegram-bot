# Expensify GitHub → Telegram Bot

Expensify/App repodagi siz uchun muhim hodisalarni Telegram'ga yuboradigan bot:

- **Sizga @mention** qilingan har qanday komment (proposalingizga javob, mention va h.k.)
- **C+ tomonidan proposal tasdiqlanishi** (`🎀 C+ reviewed`, `looks good to me`, `I'd like to propose @you` shablonlari)
- **Issue sizga assign qilinganda**

GitHub Actions ustida ishlaydi — har 5 daqiqada tekshiradi, hech qanday server kerak emas, bepul.

---

## 1-qadam: Telegram bot yaratish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga kiring
2. `/newbot` yozing
3. Bot uchun ism va username bering (username `_bot` bilan tugashi kerak, masalan `my_expensify_bot`)
4. BotFather sizga **bot tokenini** beradi — masalan `7891234567:AAH...`. Uni saqlang.

## 2-qadam: Telegram chat ID'ni olish

1. Yangi yaratilgan botingizga kiring va `/start` yozing (yoki shunchaki biror xabar yuboring)
2. Brauzerda ushbu URL'ga kiring (TOKEN o'rniga o'zingiznikini qo'ying):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Javobda `"chat":{"id": 123456789, ...}` deb yozilgan raqamni toping — bu sizning **chat ID**'ngiz.

> Eslatma: agar `getUpdates` bo'sh javob qaytarsa, botga bir necha marta xabar yozib qayta urinib ko'ring.

## 3-qadam: GitHub repo yaratish

1. [GitHub'da yangi repo yarating](https://github.com/new) — **Private** qiling (chunki state.json'da hech qanday maxfiy ma'lumot bo'lmasa-da, shaxsiy loyiha hisoblanadi)
2. Ushbu loyihaning barcha fayllarini repoga yuklang (`monitor.py`, `requirements.txt`, `.github/workflows/monitor.yml`, `.gitignore`, `README.md`)
3. Push qilib oling

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<sizning-username>/<repo-nomi>.git
git push -u origin main
```

## 4-qadam: Secrets va variables sozlash

GitHub repoyingizda **Settings → Secrets and variables → Actions** bo'limiga o'ting.

### Secrets (Repository secrets):
| Nomi | Qiymati |
|------|---------|
| `TELEGRAM_TOKEN` | BotFather bergan token (`7891234567:AAH...`) |
| `TELEGRAM_CHAT_ID` | Sizning chat ID'ngiz (`123456789`) |

### Variables (Repository variables):
| Nomi | Qiymati |
|------|---------|
| `GH_USERNAME` | Sizning GitHub username'ingiz (masalan `alibaba`) |

> `GITHUB_TOKEN` — GitHub Actions tomonidan avtomatik beriladi, qo'lda qo'shish shart emas.

## 5-qadam: Actions'ni ishga tushirish

1. Repoyingizda **Actions** tabiga o'ting
2. Birinchi marta Actions'ni yoqishni so'rasa — yoqing
3. Chap tomondan **Expensify Telegram Notifier** workflow'ni tanlang
4. **Run workflow** tugmasini bosing → yana **Run workflow**

Birinchi run ~30 sekundda tugaydi. Logni ochib `[monitor] sent ... notifs` yozuvini ko'rsangiz — hammasi ishlamoqda. Birinchi runda hozir sizga assign qilingan eski issuelar haqida xabar **yuborilmaydi** (faqat snapshot oladi), aks holda Telegram spam bo'lib ketardi. Keyingi runlardan boshlab yangi hodisalar uchun xabar keladi.

## 6-qadam: Sinash

Test qilish uchun:
- Issue ostida o'zingizga `@<username>` mention qilib komment yozing → 5 daqiqa ichida Telegramga xabar kelishi kerak
- Yoki workflow'ni qo'lda yana ishga tushiring (**Run workflow**)

---

## Texnik tafsilotlar

- **State**: `state.json` har run'da repoga commit qilinadi. Shu sayin bot eskirib qolgan kommentlarni qayta yubormaydi.
- **Rate limit**: GitHub auto-token bilan soatiga 1000 ta so'rov, biz soatiga ~60-120 ta qilamiz — limitdan uzoq.
- **Cron**: GitHub Actions schedule "5 daqiqa" deyilgan bo'lsa-da, real dunyoda 5-15 daqiqa kechikish bo'lishi mumkin (Actions navbati band bo'lganda). Bu normal.
- **Inactive repo**: agar 60 kun davomida repo'da hech qanday aktivlik bo'lmasa, GitHub schedule'larni o'chiradi. Bizning bot state.json'ni commit qilib turadi, shuning uchun bu muammo bo'lmaydi.

## Bot xabar yubormayotgan bo'lsa, tekshiring

1. Actions logini oching — error bormi?
2. Secrets to'g'ri kiritilganmi? (Token va chat_id'da bo'sh joy yo'qmi?)
3. Botga Telegram'da kamida bir marta `/start` yuborganmisiz? (Aks holda bot sizga yoza olmaydi)
4. `GH_USERNAME` — bu sizning **GitHub** loginingiz, ekran ismi emas.

## Sozlash imkoniyatlari

`monitor.py` faylida:
- `REPO = "Expensify/App"` — boshqa repolarni kuzatish uchun o'zgartiring
- `INITIAL_LOOKBACK_HOURS = 6` — birinchi runda qancha vaqt orqaga qarash
- `classify_comment()` funksiyasini o'zgartirib, boshqa shablonlarni ham aniqlashga qo'shishingiz mumkin

`.github/workflows/monitor.yml` faylida:
- `cron: '*/5 * * * *'` — tekshirish chastotasi (GitHub minimal 5 daqiqa)

Omad! 🎀
