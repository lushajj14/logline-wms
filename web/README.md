# LOGLine Web Dashboard

PyQt uygulamasının web versiyonu. Mevcut masaüstü uygulamasını bozmadan paralel çalışır.

## 📁 Klasör Yapısı

```
web/
├── backend/           # FastAPI web server
│   ├── main.py       # Web API endpoints
│   └── routers/      # Modüler API routes
├── frontend/         # React uygulaması
│   ├── src/
│   │   ├── pages/    # Dashboard, Login vs.
│   │   ├── components/ # Yeniden kullanılabilir components
│   │   └── services/ # API calls
│   └── package.json
└── shared/           # Ortak modüller (DAO'lar vs.)
```

## 🚀 Geliştirme Ortamı

### Backend (FastAPI)
```bash
cd web/backend
python main.py
# http://localhost:8002
```

### Frontend (React)
```bash
cd web/frontend
npm install
npm start
# http://localhost:3000
```

## 🔄 Deployment Stratejisi

1. **Geliştirme**: Farklı portlarda paralel çalışma
2. **Production**: Tek portta (8000) birleştirilecek
3. **Mevcut Mobil API**: Hiç etkilenmeyecek

## 📋 İlerleme

- [x] Klasör yapısı oluşturuldu
- [x] React uygulaması kuruldu  
- [x] Dashboard sayfası hazırlandı
- [x] Login sayfası oluşturuldu
- [x] FastAPI backend başlatıldı
- [ ] DAO entegrasyonu
- [ ] Production build
- [ ] Tek port deployment

## 🎯 Hedefler

- PyQt uygulamasının aynısını web'de
- Responsive tasarım
- Mobil uyumlu
- Aynı veritabanı ve kullanıcı sistemi