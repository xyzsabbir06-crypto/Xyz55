SABBIR XYZ SHOP — MAIN CODE
===========================

ZIP contents:
- bot.py
- requirements.txt
- README_BANGLA.txt

SETUP
-----
1. Render-এর Environment Variables-এ BOT_TOKEN নামে নিজের নতুন BotFather token দিন। Token কোডে লিখবেন না।
2. PAYVORA_API_KEY-এ নিজের PayVora API key বসান।
3. PAYVORA_WEBHOOK_URL-এ hosting-এর public HTTPS callback URL বসান, যা এই bot-এর webhook endpoint-এ পৌঁছায়। PayVora documentation/hosting অনুযায়ী URL ঠিক করুন।
4. requirements.txt-এর dependencies install করে bot.py চালু করুন।
5. Admin Panel > Payment Settings থেকে PayVora Auto Payment ON রাখুন।

PAYMENT FLOW
------------
- Add Balance বা Buy Now থেকে PayVora payment link তৈরি হবে।
- Customer PAY NOW চাপ দিয়ে gateway-তে payment complete করবে।
- Bot webhook থাকলে callback দিয়ে এবং fallback হিসেবে প্রতি ২০ সেকেন্ডে check_invoice API poll করে status যাচাই করবে।
- API-তে payment paid/success/completed দেখালে এবং amount invoice-এর সঙ্গে মিললে balance add বা product delivery হবে; একই payment দুবার process না করার জন্য database status/transaction check আছে।
- User-কে আলাদা VERIFY PAYMENT button দেখানো হয় না।
- Payment checkout message-এ বাংলা ও English নির্দেশনা রয়েছে।
- Product-loading animation বন্ধ; payment-link, delivery এবং Lucky Spin animation রাখা হয়েছে।
- Manual payment/admin features মূল bot code-এ রাখা হয়েছে।

IMPORTANT
---------
- API key, bot token এবং webhook URL এই package-এ secret হিসেবে embed করা হয়নি; নিজের configuration বসাতে হবে।
- Syntax এবং ZIP integrity পরীক্ষা করা হয়েছে, কিন্তু live PayVora payment সফলভাবে test করা হয়নি। প্রথমে ছোট অঙ্কে test করুন।
- যদি PayVora API request-কে browser signature/WAF কারণে block করে, PayVora support-কে server-side API access allow করতে বলুন; শুধু code বদলালেই তাদের security block নিশ্চিতভাবে উঠবে না।
- Token/API key প্রকাশ হয়ে থাকলে rotate করে নতুন key ব্যবহার করুন।

RENDER CONFIG
-------------
This is a Python Telegram bot using long polling. Deploy as a Background Worker, not a Go service.
Build Command: pip install -r requirements.txt
Start Command: python bot.py
Environment Variable: BOT_TOKEN=<your new BotFather token>
