# User Guide — Farmers, FPOs & Extension Staff

## 1. For Farmers (WhatsApp & Web Voice Simulator)
1. **Send a voice note or text message** in **Marathi**, **Hindi**, **English**, or mixed language (e.g., *"माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?"* or *"नागपुर में आज मौसम कैसा रहेगा?"*).
2. **Listen to the voice reply**: You will receive a short, simple spoken answer (under 30 seconds) along with the **source name** (e.g., *ICAR-CICR Nagpur*) and, for mandi prices or weather, the **data as of** date.
3. **If the assistant asks you to repeat**: Move to a quieter spot and record your question again clearly.
4. **If the assistant says "I am not sure"**: It means verified sources did not cover your exact question. Call the **Kisan Call Centre (1800-180-1551)** or visit your nearest **Krishi Vigyan Kendra (KVK)**.
5. **Chemical & Pesticide Safety**: Guidance is informational only. Always read the product label, wear gloves and a mask, and confirm dosages with your local KVK before spraying.

## 2. For Admins, Reviewers & Analysts (Web Console)
Open `http://localhost:8000`:
- **Farmer Simulator**: Test text/voice queries, inspect confidence scores and source citations, and submit thumbs-up/down feedback.
- **Knowledge Base**: Review ingested bulletins, verify source/licence/publication date, and click **Approve** or **Reject**. Only approved documents are used in answers.
- **Glossary**: Add regional Hindi and Marathi agricultural terms so crop, pest, and chemical names are never mistranslated.
- **Eval & Review**: Run the automated evaluation benchmark and inspect low-confidence or refused queries in the Expert Review Queue.
