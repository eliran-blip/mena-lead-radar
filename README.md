# MENA Lead Radar 🌍

סריקה יומית אוטומטית של חברות עם כוונת כניסה לשווקי GCC · ירדן · מצרים

---

## מה זה עושה?

כל יום בשעה 07:00 (שעון ישראל), המערכת:
1. סורקת עשרות מקורות חדשות בינלאומיים
2. מזהה חברות עם סיגנלים של כניסה לשווקי ה-MENA
3. מדרגת כל ליד (חם / פושר / קר)
4. כותבת את הרשימה ישירות ל-Google Sheet שלך

---

## הגדרה — 4 שלבים (כ-15 דקות)

---

### שלב 1 — קבל NewsAPI Key (חינם)

1. כנס ל-[newsapi.org](https://newsapi.org)
2. לחץ **Get API Key**
3. הירשם עם אימייל
4. תקבל מפתח כזה: `abc123def456...`
5. שמור אותו — תצטרך אותו בשלב 4

---

### שלב 2 — הגדר Google Sheet

1. כנס ל-[sheets.google.com](https://sheets.google.com)
2. צור גיליון חדש — שם אותו **MENA Leads**
3. העתק את ה-**Sheet ID** מה-URL:
   ```
   https://docs.google.com/spreadsheets/d/  →  1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms  ←  /edit
   ```
4. שמור את ה-ID הזה

---

### שלב 3 — הגדר Google Service Account

> זה מאפשר לקוד לכתוב ל-Sheet שלך אוטומטית.

1. כנס ל-[console.cloud.google.com](https://console.cloud.google.com)
2. צור פרויקט חדש — שם לו `mena-radar`
3. לחץ **APIs & Services → Enable APIs**
4. חפש **Google Sheets API** ולחץ Enable
5. לחץ **APIs & Services → Credentials**
6. לחץ **Create Credentials → Service Account**
7. שם: `mena-radar-bot` → לחץ Done
8. לחץ על ה-Service Account שיצרת
9. לחץ **Keys → Add Key → Create New Key → JSON**
10. יורד קובץ JSON — שמור אותו
11. פתח את קובץ ה-JSON — **העתק את כל התוכן**

**חשוב:** שתף את ה-Google Sheet עם ה-Service Account:
- פתח את ה-Sheet
- לחץ Share
- הוסף את האימייל של ה-Service Account (נראה כך: `mena-radar-bot@mena-radar.iam.gserviceaccount.com`)
- תן הרשאת **Editor**

---

### שלב 4 — הגדר Secrets ב-GitHub

1. כנס ל-repository שלך ב-GitHub
2. לחץ **Settings → Secrets and variables → Actions**
3. לחץ **New repository secret** — הוסף 3 secrets:

| שם Secret | ערך |
|-----------|-----|
| `NEWS_API_KEY` | המפתח מ-newsapi.org |
| `GOOGLE_SHEET_ID` | ה-ID של ה-Sheet |
| `GOOGLE_CREDENTIALS_JSON` | כל תוכן קובץ ה-JSON (העתק הכל) |

---

## הרצה ידנית לבדיקה

אחרי שהגדרת הכל:
1. כנס ל-**Actions** ב-GitHub
2. בחר **MENA Lead Radar — Daily Scan**
3. לחץ **Run workflow**
4. חכה כ-2 דקות
5. פתח את ה-Google Sheet — תראה לידים חדשים!

---

## מה מופיע ב-Google Sheet?

| עמודה | תוכן |
|-------|------|
| תאריך | מתי נסרק |
| חברה | שם החברה שזוהתה |
| סיגנל | הכותרת שהפעילה את הזיהוי |
| שוק יעד | סעודיה / UAE / מצרים וכו' |
| מקור | Reuters / Bloomberg / LinkedIn וכו' |
| קישור | לינק לכתבה המקורית |
| דירוג | 0-99 |
| חום | hot / warm / cold |
| זרוע | IL / EU / AR |
| סיגנלים | מילות המפתח שזוהו |
| סטטוס | new (לשינוי ידני) |
| אושר? | לסימון שלך |
| איש קשר | למילוי ידני |
| תפקיד | למילוי ידני |
| אימייל | למילוי ידני |
| הערות | למילוי ידני |

---

## לוגיקת הדירוג

**חם 🔴 (75+)**
- ציון גבוה ממספר סיגנלים חזקים
- סיגנלים: market entry, first launch, distributor, new office, regulatory approval

**פושר 🟡 (55-74)**
- כוונה מוצהרת אבל פחות ספציפית
- סיגנלים: expansion, partnership, funding with MENA mention

**קר 🔵 (מתחת ל-55)**
- אזכור אגבי בלבד
- דורש בדיקה נוספת לפני פנייה

---

## לוח זמנים

```
כל יום 07:00 (שעון ישראל)
→ GitHub Actions מריץ את הסקריפט
→ ~2 דקות עיבוד
→ Google Sheet מתעדכן
→ אתה מסנן ב-5 דקות
→ הצוות מקבל רשימה נקייה
```

---

## שאלות נפוצות

**כמה לידים לצפות ביום?**
15-40 לידים מסוננים ביום, תלוי בפעילות החדשותית.

**האם זה עולה כסף?**
לא. GitHub Actions חינם, NewsAPI Developer Plan חינם (500 בקשות/יום), Google Sheets חינם.

**מה קורה אם הסריקה נכשלת?**
GitHub שולח מייל אוטומטי. אפשר להריץ ידנית מ-Actions.

---

## הרחבות עתידיות (שלב 2)

- [ ] LinkedIn Jobs scanning
- [ ] אנשי קשר אוטומטיים
- [ ] התראת WhatsApp ליד חם
- [ ] ניתוח מגמות שבועי
- [ ] דשבורד ויזואלי

---

*MENA Markets · Powered by GitHub Actions + NewsAPI + Google Sheets*
