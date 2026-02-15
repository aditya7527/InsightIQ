from fastapi import APIRouter
from app.database import engine
from app.models import reports, admin_metrics
from sqlalchemy import select, func, insert, update

router = APIRouter(tags=["Admin"])


@router.get('/admin/metrics')
def get_metrics():
    """
    Get admin metrics including reports generated and average latency
    """
    with engine.connect() as conn:
        # Get reports count
        try:
            r_count = conn.execute(select(func.count()).select_from(reports)).scalar()
        except Exception:
            r_count = 0
        
        # Get metrics row
        try:
            metrics = conn.execute(select(admin_metrics)).fetchone()
            # Handle both dictionary access (mappings) and object access if needed
            if metrics:
                # SQLAlchemy rows can be accessed by column name
                avg_latency = metrics.avg_latency_ms
            else:
                avg_latency = 0
        except Exception:
            avg_latency = 0
            
    return {"reports_generated": r_count or 0, "avg_latency_ms": float(avg_latency) if avg_latency else 0.0}


@router.post('/admin/metrics/increment')
def increment_report_count(latency_ms: float = 0.0):
    """
    Increment the report count and update average latency
    """
    with engine.begin() as conn:
        r = conn.execute(select(admin_metrics)).first()
        if not r:
            conn.execute(insert(admin_metrics).values(reports_generated=1, avg_latency_ms=latency_ms))
            new_count = 1
        else:
            # SQLAlchemy 1.4+ row mapping access
            cur_count = r.reports_generated or 0
            prev_avg = r.avg_latency_ms or 0.0
            
            new_count = cur_count + 1
            new_avg = (prev_avg + latency_ms) / 2 if new_count > 1 else latency_ms
            
            conn.execute(update(admin_metrics).values(reports_generated=new_count, avg_latency_ms=new_avg))
            
    return {"status": "ok", "reports_generated": new_count}
