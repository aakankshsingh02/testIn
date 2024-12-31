from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from ..config import settings

Base = declarative_base()

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float)
    quantity = Column(Integer)
    trade_type = Column(String)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime)
    pnl = Column(Float)

class Alert(Base):
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    price_target = Column(Float)
    alert_type = Column(String)
    triggered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(settings.DB_URL)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.SessionLocal()
    
    def record_trade(self, trade_data: dict):
        with self.get_session() as session:
            trade = Trade(**trade_data)
            session.add(trade)
            session.commit()
    
    def get_trades(self, symbol: str = None, limit: int = None):
        with self.get_session() as session:
            query = session.query(Trade)
            if symbol:
                query = query.filter(Trade.symbol == symbol)
            if limit:
                query = query.limit(limit)
            return query.all()
    
    def add_alert(self, alert_data: dict):
        with self.get_session() as session:
            alert = Alert(**alert_data)
            session.add(alert)
            session.commit()
    
    def get_active_alerts(self, symbol: str = None):
        with self.get_session() as session:
            query = session.query(Alert).filter(Alert.triggered == False)
            if symbol:
                query = query.filter(Alert.symbol == symbol)
            return query.all()

db_manager = DatabaseManager()