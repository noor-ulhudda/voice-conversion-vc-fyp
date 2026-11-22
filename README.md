# voice-conversion-vc-fyp

```
voice-conversion-vc-fyp/
├── frontend/              <- deploy this folder on Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   └── config.js          <- put your ngrok URL here
└── backend/
    ├── kaggle_backend.ipynb   <- upload to Kaggle, runs the API on a free GPU
    ├── main.py                <- FastAPI server (already embedded in the notebook)
    ├── prep_models.py         <- downloads the 4 speaker models (embedded in the notebook)
    └── requirements.txt
```
Voices: speaker 1 = old man, 2 = old woman, 3 = mid-age man, 4 = mid-age woman.
Follow the step-by-step guide given in chat.
