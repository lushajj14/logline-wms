import React, { useState, useEffect } from 'react';
import { dashboardAPI, handleApiError, getCurrentUser } from '../services/api';

const Dashboard = () => {
  const [stats, setStats] = useState({
    orders: 0,
    items: 0,
    users: 0,
    activities: 0,
    alerts: 0,
    warehouse: 0
  });
  
  const [systemStatus, setSystemStatus] = useState({
    database: { status: 'Kontrol ediliyor...', connected: false },
    pool: { active: 0, max: 10, usage: 0 },
    logo_db: { status: 'Kontrol ediliyor...', last_sync: 'Bilinmiyor' }
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activities, setActivities] = useState([]);
  const [user] = useState(getCurrentUser());

  useEffect(() => {
    fetchDashboardData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Parallel API calls
      const [statsResponse, statusResponse, activitiesResponse] = await Promise.all([
        dashboardAPI.getStats(),
        dashboardAPI.getSystemStatus(),
        dashboardAPI.getRecentActivities(5)
      ]);

      setStats(statsResponse.data);
      setSystemStatus(statusResponse.data);
      setActivities(activitiesResponse.data);
      
    } catch (error) {
      console.error('Dashboard verisi yüklenemedi:', error);
      const errorInfo = handleApiError(error);
      setError(errorInfo.message);
      
      // Fallback data on error
      setStats({
        orders: 'N/A', items: 'N/A', users: 'N/A',
        activities: 'N/A', alerts: 'N/A', warehouse: 'N/A'
      });
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num/1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num/1000).toFixed(1)}K`;
    return num.toString();
  };

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <div className="sidebar">
        <h2>🏢 LOGLine</h2>
        <ul>
          <li className="active">📊 Dashboard</li>
          <li>📋 Pick-List</li>
          <li>🔍 Scanner</li>
          <li>📦 Back-Orders</li>
          <li>📈 Rapor</li>
          <li>🏷️ Etiket</li>
          <li>📁 Loader</li>
          <li>🚛 Sevkiyat</li>
          <li>⚙️ Ayarlar</li>
        </ul>
      </div>

      {/* Main Content */}
      <div className="main-content">
        {/* Header */}
        <div className="header">
          <div>
            <h1>Dashboard</h1>
            {user && <p style={{ margin: 0, color: '#666', fontSize: '14px' }}>
              Hoş geldin, {user.full_name} ({user.role})
            </p>}
          </div>
          <div>
            {error && <span style={{ color: '#e74c3c', marginRight: '10px', fontSize: '14px' }}>
              ⚠️ {error}
            </span>}
            <button className="refresh-btn" onClick={fetchDashboardData} disabled={loading}>
              {loading ? '🔄 Yükleniyor...' : '🔄 Yenile'}
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="stats-grid">
          <div className="stat-card orders">
            <div className="icon">📦</div>
            <h3>Toplam Sipariş</h3>
            <div className="value">{formatNumber(stats.orders)}</div>
          </div>
          
          <div className="stat-card items">
            <div className="icon">📋</div>
            <h3>Stok Kalemleri</h3>
            <div className="value">{formatNumber(stats.items)}</div>
          </div>
          
          <div className="stat-card users">
            <div className="icon">👥</div>
            <h3>Aktif Kullanıcı</h3>
            <div className="value">{stats.users}</div>
          </div>
          
          <div className="stat-card activities">
            <div className="icon">📈</div>
            <h3>Bugün Aktivite</h3>
            <div className="value">{stats.activities}</div>
          </div>
          
          <div className="stat-card alerts">
            <div className="icon">⚠️</div>
            <h3>Sistem Uyarı</h3>
            <div className="value">{stats.alerts}</div>
          </div>
          
          <div className="stat-card warehouse">
            <div className="icon">🏭</div>
            <h3>Ambar İşlem</h3>
            <div className="value">{stats.warehouse}</div>
          </div>
        </div>

        {/* Bottom Panels */}
        <div className="bottom-panels">
          {/* Activities Panel */}
          <div className="panel">
            <h3>Son Kullanıcı Aktiviteleri</h3>
            <div className="panel-content">
              {loading ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                  🔄 Aktiviteler yükleniyor...
                </div>
              ) : activities.length > 0 ? (
                activities.map((activity, index) => (
                  <div key={index} className="status-item">
                    <span>👤 {activity.username} - {activity.action}</span>
                    <span>{activity.time_ago}</span>
                  </div>
                ))
              ) : (
                <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                  📝 Henüz aktivite kaydı yok
                </div>
              )}
            </div>
          </div>

          {/* System Status Panel */}
          <div className="panel">
            <h3>Sistem Durumu</h3>
            <div className="panel-content">
              <div className="status-item">
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div className={`status-indicator ${systemStatus.database.connected ? 'connected' : 'error'}`}></div>
                  <span>🗄️ Veritabanı</span>
                </div>
                <span>{systemStatus.database.status}</span>
              </div>
              
              <div className="status-item">
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div className="status-indicator connected"></div>
                  <span>🔗 Connection Pool</span>
                </div>
                <span>{systemStatus.pool.active}/{systemStatus.pool.max}</span>
              </div>
              
              <div className="status-item">
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div className={`status-indicator ${systemStatus.logo_db.status === 'Bağlı' ? 'connected' : 'error'}`}></div>
                  <span>🏢 LOGO DB</span>
                </div>
                <span>{systemStatus.logo_db.status}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;