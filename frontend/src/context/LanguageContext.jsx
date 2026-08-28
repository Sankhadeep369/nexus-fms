import { createContext, useContext, useEffect, useMemo, useState } from "react";

// PURELY a UI/UX layer: translates the interface chrome only. The chat pipeline,
// the queries sent to the backend, and the AI's answers are untouched (they stay
// English) — nothing here calls the backend or affects response timing. Any string
// without a translation falls back to English.
const KEY = "nexus-lang";

// English (default) + top 10 non-Indian + top 10 Indian languages.
export const LANGUAGES = [
  { code: "en", native: "English", dir: "ltr", group: "Default" },
  { code: "es", native: "Español", dir: "ltr", group: "International" },
  { code: "fr", native: "Français", dir: "ltr", group: "International" },
  { code: "de", native: "Deutsch", dir: "ltr", group: "International" },
  { code: "zh", native: "中文", dir: "ltr", group: "International" },
  { code: "ar", native: "العربية", dir: "rtl", group: "International" },
  { code: "pt", native: "Português", dir: "ltr", group: "International" },
  { code: "ru", native: "Русский", dir: "ltr", group: "International" },
  { code: "ja", native: "日本語", dir: "ltr", group: "International" },
  { code: "id", native: "Bahasa Indonesia", dir: "ltr", group: "International" },
  { code: "it", native: "Italiano", dir: "ltr", group: "International" },
  { code: "hi", native: "हिन्दी", dir: "ltr", group: "Indian" },
  { code: "bn", native: "বাংলা", dir: "ltr", group: "Indian" },
  { code: "te", native: "తెలుగు", dir: "ltr", group: "Indian" },
  { code: "mr", native: "मराठी", dir: "ltr", group: "Indian" },
  { code: "ta", native: "தமிழ்", dir: "ltr", group: "Indian" },
  { code: "ur", native: "اردو", dir: "rtl", group: "Indian" },
  { code: "gu", native: "ગુજરાતી", dir: "ltr", group: "Indian" },
  { code: "kn", native: "ಕನ್ನಡ", dir: "ltr", group: "Indian" },
  { code: "ml", native: "മലയാളം", dir: "ltr", group: "Indian" },
  { code: "pa", native: "ਪੰਜਾਬੀ", dir: "ltr", group: "Indian" },
];

// Core interface strings. Keys missing for a language fall back to English.
const STRINGS = {
  en: { tab_chat: "Chat", tab_agents: "Agents", tab_analysis: "Analysis", tab_dashboard: "Dashboard", tab_admin: "Admin", input_placeholder: "Message NEXUS", mode_simple: "Simple", mode_thinking: "Thinking", new_chat: "New chat", search_chats: "Search chats", sign_in: "Sign in", try_example: "Try an example", see_how: "See how it works", language: "Language" },
  es: { tab_chat: "Chat", tab_agents: "Agentes", input_placeholder: "Escribe a NEXUS", mode_simple: "Simple", mode_thinking: "Reflexivo", new_chat: "Nuevo chat", search_chats: "Buscar chats", sign_in: "Iniciar sesión", try_example: "Prueba un ejemplo", see_how: "Cómo funciona", language: "Idioma" },
  fr: { tab_chat: "Chat", tab_agents: "Agents", input_placeholder: "Écrire à NEXUS", mode_simple: "Simple", mode_thinking: "Réflexion", new_chat: "Nouvelle discussion", search_chats: "Rechercher", sign_in: "Se connecter", try_example: "Essayer un exemple", see_how: "Comment ça marche", language: "Langue" },
  de: { tab_chat: "Chat", tab_agents: "Agenten", input_placeholder: "Nachricht an NEXUS", mode_simple: "Einfach", mode_thinking: "Nachdenken", new_chat: "Neuer Chat", search_chats: "Chats suchen", sign_in: "Anmelden", try_example: "Beispiel ausprobieren", see_how: "So funktioniert es", language: "Sprache" },
  zh: { tab_chat: "对话", tab_agents: "智能体", input_placeholder: "给 NEXUS 发消息", mode_simple: "简洁", mode_thinking: "深入", new_chat: "新对话", search_chats: "搜索对话", sign_in: "登录", try_example: "试试示例", see_how: "使用指南", language: "语言" },
  ar: { tab_chat: "محادثة", tab_agents: "الوكلاء", input_placeholder: "راسل NEXUS", mode_simple: "بسيط", mode_thinking: "تفكير", new_chat: "محادثة جديدة", search_chats: "بحث في المحادثات", sign_in: "تسجيل الدخول", try_example: "جرّب مثالاً", see_how: "كيف يعمل", language: "اللغة" },
  pt: { tab_chat: "Chat", tab_agents: "Agentes", input_placeholder: "Mensagem para NEXUS", mode_simple: "Simples", mode_thinking: "Reflexivo", new_chat: "Nova conversa", search_chats: "Pesquisar conversas", sign_in: "Entrar", try_example: "Experimente um exemplo", see_how: "Como funciona", language: "Idioma" },
  ru: { tab_chat: "Чат", tab_agents: "Агенты", input_placeholder: "Написать NEXUS", mode_simple: "Просто", mode_thinking: "Размышление", new_chat: "Новый чат", search_chats: "Поиск чатов", sign_in: "Войти", try_example: "Попробуйте пример", see_how: "Как это работает", language: "Язык" },
  ja: { tab_chat: "チャット", tab_agents: "エージェント", input_placeholder: "NEXUS にメッセージ", mode_simple: "シンプル", mode_thinking: "熟考", new_chat: "新しいチャット", search_chats: "チャットを検索", sign_in: "ログイン", try_example: "例を試す", see_how: "使い方", language: "言語" },
  id: { tab_chat: "Obrolan", tab_agents: "Agen", input_placeholder: "Kirim pesan ke NEXUS", mode_simple: "Sederhana", mode_thinking: "Berpikir", new_chat: "Obrolan baru", search_chats: "Cari obrolan", sign_in: "Masuk", try_example: "Coba contoh", see_how: "Cara kerjanya", language: "Bahasa" },
  it: { tab_chat: "Chat", tab_agents: "Agenti", input_placeholder: "Scrivi a NEXUS", mode_simple: "Semplice", mode_thinking: "Riflessione", new_chat: "Nuova chat", search_chats: "Cerca chat", sign_in: "Accedi", try_example: "Prova un esempio", see_how: "Come funziona", language: "Lingua" },
  hi: { tab_chat: "चैट", tab_agents: "एजेंट", input_placeholder: "NEXUS को संदेश भेजें", mode_simple: "सरल", mode_thinking: "विचारशील", new_chat: "नई चैट", search_chats: "चैट खोजें", sign_in: "साइन इन करें", try_example: "उदाहरण आज़माएँ", see_how: "यह कैसे काम करता है", language: "भाषा" },
  bn: { tab_chat: "চ্যাট", tab_agents: "এজেন্ট", input_placeholder: "NEXUS-কে বার্তা দিন", mode_simple: "সরল", mode_thinking: "চিন্তাশীল", new_chat: "নতুন চ্যাট", search_chats: "চ্যাট খুঁজুন", sign_in: "সাইন ইন", try_example: "একটি উদাহরণ দেখুন", see_how: "এটি কীভাবে কাজ করে", language: "ভাষা" },
  te: { tab_chat: "చాట్", tab_agents: "ఏజెంట్లు", input_placeholder: "NEXUSకి సందేశం", mode_simple: "సరళం", mode_thinking: "ఆలోచన", new_chat: "కొత్త చాట్", search_chats: "చాట్‌లను వెతకండి", sign_in: "సైన్ ఇన్", try_example: "ఉదాహరణ ప్రయత్నించండి", see_how: "ఇది ఎలా పనిచేస్తుంది", language: "భాష" },
  mr: { tab_chat: "चॅट", tab_agents: "एजंट", input_placeholder: "NEXUS ला संदेश", mode_simple: "सोपे", mode_thinking: "विचारशील", new_chat: "नवीन चॅट", search_chats: "चॅट शोधा", sign_in: "साइन इन", try_example: "उदाहरण वापरून पहा", see_how: "हे कसे कार्य करते", language: "भाषा" },
  ta: { tab_chat: "அரட்டை", tab_agents: "முகவர்கள்", input_placeholder: "NEXUS-க்கு செய்தி", mode_simple: "எளிது", mode_thinking: "சிந்தனை", new_chat: "புதிய அரட்டை", search_chats: "அரட்டைகளைத் தேடு", sign_in: "உள்நுழை", try_example: "எடுத்துக்காட்டை முயற்சிக்கவும்", see_how: "இது எப்படி வேலை செய்கிறது", language: "மொழி" },
  ur: { tab_chat: "چیٹ", tab_agents: "ایجنٹس", input_placeholder: "NEXUS کو پیغام", mode_simple: "سادہ", mode_thinking: "غور و فکر", new_chat: "نئی چیٹ", search_chats: "چیٹ تلاش کریں", sign_in: "سائن ان", try_example: "ایک مثال آزمائیں", see_how: "یہ کیسے کام کرتا ہے", language: "زبان" },
  gu: { tab_chat: "ચેટ", tab_agents: "એજન્ટ્સ", input_placeholder: "NEXUS ને સંદેશ", mode_simple: "સરળ", mode_thinking: "વિચારશીલ", new_chat: "નવી ચેટ", search_chats: "ચેટ શોધો", sign_in: "સાઇન ઇન", try_example: "ઉદાહરણ અજમાવો", see_how: "તે કેવી રીતે કામ કરે છે", language: "ભાષા" },
  kn: { tab_chat: "ಚಾಟ್", tab_agents: "ಏಜೆಂಟ್‌ಗಳು", input_placeholder: "NEXUS ಗೆ ಸಂದೇಶ", mode_simple: "ಸರಳ", mode_thinking: "ಚಿಂತನೆ", new_chat: "ಹೊಸ ಚಾಟ್", search_chats: "ಚಾಟ್‌ಗಳನ್ನು ಹುಡುಕಿ", sign_in: "ಸೈನ್ ಇನ್", try_example: "ಉದಾಹರಣೆ ಪ್ರಯತ್ನಿಸಿ", see_how: "ಇದು ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ", language: "ಭಾಷೆ" },
  ml: { tab_chat: "ചാറ്റ്", tab_agents: "ഏജന്റുകൾ", input_placeholder: "NEXUS-ന് സന്ദേശം", mode_simple: "ലളിതം", mode_thinking: "ചിന്ത", new_chat: "പുതിയ ചാറ്റ്", search_chats: "ചാറ്റുകൾ തിരയുക", sign_in: "സൈൻ ഇൻ", try_example: "ഒരു ഉദാഹരണം പരീക്ഷിക്കുക", see_how: "ഇത് എങ്ങനെ പ്രവർത്തിക്കുന്നു", language: "ഭാഷ" },
  pa: { tab_chat: "ਚੈਟ", tab_agents: "ਏਜੰਟ", input_placeholder: "NEXUS ਨੂੰ ਸੁਨੇਹਾ", mode_simple: "ਸਧਾਰਨ", mode_thinking: "ਸੋਚ", new_chat: "ਨਵੀਂ ਚੈਟ", search_chats: "ਚੈਟ ਖੋਜੋ", sign_in: "ਸਾਈਨ ਇਨ", try_example: "ਇੱਕ ਉਦਾਹਰਨ ਅਜ਼ਮਾਓ", see_how: "ਇਹ ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ", language: "ਭਾਸ਼ਾ" },
};

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    const saved = localStorage.getItem(KEY);
    return LANGUAGES.some((l) => l.code === saved) ? saved : "en";
  });

  useEffect(() => {
    const meta = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0];
    document.documentElement.lang = meta.code;
    document.documentElement.dir = meta.dir;
    localStorage.setItem(KEY, lang);
  }, [lang]);

  const value = useMemo(
    () => ({
      lang,
      setLang,
      t: (key) => STRINGS[lang]?.[key] ?? STRINGS.en[key] ?? key,
    }),
    [lang]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}
