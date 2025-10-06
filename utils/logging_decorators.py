"""
Logging decorators for calculation functions with input/output snapshots
"""
import uuid
import json
import time
import traceback
from functools import wraps
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from db.session import SessionLocal
from models.calculation_log import CalculationLog
from models.tax_parameters import TaxParameters
from datetime import datetime

def log_calculation(function):
    """
    Decorator to log calculation function calls with input/output snapshots
    """
    @wraps(function)
    def wrapper(*args, **kwargs):
        trace_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Extract client_id if available
        client_id = get_client_id_from_args(args, kwargs)
        
        # Serialize inputs
        input_snapshot = serialize_inputs(args, kwargs)
        
        # Get current tax parameters snapshot
        tax_snapshot = get_current_tax_parameters_snapshot()
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Execute the function
            result = function(*args, **kwargs)
            
            # Calculate execution time
            execution_time = int((time.time() - start_time) * 1000)
            
            # Serialize output
            output_snapshot = serialize_output(result)
            
            # Log successful execution
            log_entry = CalculationLog(
                trace_id=trace_id,
                client_id=client_id,
                function_name=function.__name__,
                input_snapshot=input_snapshot,
                output_snapshot=output_snapshot,
                tax_snapshot=tax_snapshot,
                execution_time_ms=execution_time,
                status="success"
            )
            
            db.add(log_entry)
            db.commit()
            
            return result
            
        except Exception as e:
            # Calculate execution time
            execution_time = int((time.time() - start_time) * 1000)
            
            # Log error
            log_entry = CalculationLog(
                trace_id=trace_id,
                client_id=client_id,
                function_name=function.__name__,
                input_snapshot=input_snapshot,
                output_snapshot=None,
                tax_snapshot=tax_snapshot,
                execution_time_ms=execution_time,
                status="error",
                error_message=str(e) + "\n" + traceback.format_exc()
            )
            
            db.add(log_entry)
            db.commit()
            
            # Re-raise the exception
            raise
            
        finally:
            db.close()
    
    return wrapper

def get_client_id_from_args(args: tuple, kwargs: dict) -> int:
    """Extract client_id from function arguments"""
    
    # Check kwargs first
    if 'client_id' in kwargs:
        return kwargs['client_id']
    
    # Check if first argument has client_id attribute
    if args and hasattr(args[0], 'client_id'):
        return args[0].client_id
    
    # Check if any argument is a Session and second argument has client_id
    for i, arg in enumerate(args):
        if isinstance(arg, Session) and i + 1 < len(args):
            next_arg = args[i + 1]
            if isinstance(next_arg, int):  # Assume it's client_id
                return next_arg
            elif hasattr(next_arg, 'client_id'):
                return next_arg.client_id
    
    return None

def serialize_inputs(args: tuple, kwargs: dict) -> str:
    """Serialize function inputs to JSON string"""
    
    serialized_args = []
    serialized_kwargs = {}
    
    # Serialize positional arguments
    for arg in args:
        serialized_args.append(serialize_value(arg))
    
    # Serialize keyword arguments
    for key, value in kwargs.items():
        serialized_kwargs[key] = serialize_value(value)
    
    return json.dumps({
        "args": serialized_args,
        "kwargs": serialized_kwargs
    }, default=str, ensure_ascii=False)

def serialize_output(result: Any) -> str:
    """Serialize function output to JSON string"""
    return json.dumps(serialize_value(result), default=str, ensure_ascii=False)

def serialize_value(value: Any) -> Any:
    """Serialize a single value, handling various types"""
    
    # Handle None
    if value is None:
        return None
    
    # Handle basic types
    if isinstance(value, (str, int, float, bool)):
        return value
    
    # Handle lists and tuples
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    
    # Handle dictionaries
    if isinstance(value, dict):
        return {key: serialize_value(val) for key, val in value.items()}
    
    # Handle SQLAlchemy Session (don't serialize)
    if hasattr(value, 'query'):
        return "<SQLAlchemy Session>"
    
    # Handle SQLAlchemy models
    if hasattr(value, '__table__'):
        return {
            "model": value.__class__.__name__,
            "id": getattr(value, 'id', None),
            "attributes": {
                key: serialize_value(getattr(value, key))
                for key in value.__table__.columns.keys()
                if hasattr(value, key)
            }
        }
    
    # Handle datetime objects
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    
    # Handle Decimal objects
    if hasattr(value, 'quantize'):
        return float(value)
    
    # Fallback to string representation
    return str(value)

def get_current_tax_parameters_snapshot() -> str:
    """Get current tax parameters as JSON snapshot"""
    
    db = SessionLocal()
    try:
        # Get the most recent tax parameters
        latest_params = db.query(TaxParameters).order_by(
            TaxParameters.valid_from.desc()
        ).first()
        
        if latest_params:
            return latest_params.json_payload
        else:
            # Return default parameters if none found
            default_params = {
                "version": "default",
                "valid_from": datetime.now().isoformat(),
                "tax_brackets": [
                    {"min": 0, "max": 75960, "rate": 0.10},
                    {"min": 75960, "max": 108840, "rate": 0.14},
                    {"min": 108840, "max": 174840, "rate": 0.20},
                    {"min": 174840, "max": 243720, "rate": 0.31},
                    {"min": 243720, "max": 507600, "rate": 0.35},
                    {"min": 507600, "rate": 0.47}
                ],
                "exemption_amounts": {
                    "personal": 2640,
                    "spouse": 2640,
                    "child": 2640
                }
            }
            return json.dumps(default_params, ensure_ascii=False)
    
    finally:
        db.close()

def run_from_log(trace_id: str) -> Dict[str, Any]:
    """
    Recreate calculation from log entry using stored snapshots
    """
    
    db = SessionLocal()
    try:
        # Get log entry
        log_entry = db.query(CalculationLog).filter(
            CalculationLog.trace_id == trace_id
        ).first()
        
        if not log_entry:
            raise ValueError(f"No log entry found for trace_id: {trace_id}")
        
        # Parse input snapshot
        input_data = json.loads(log_entry.input_snapshot)
        
        # Parse tax snapshot
        tax_data = json.loads(log_entry.tax_snapshot)
        
        return {
            "trace_id": trace_id,
            "function_name": log_entry.function_name,
            "client_id": log_entry.client_id,
            "input_data": input_data,
            "tax_parameters": tax_data,
            "original_output": json.loads(log_entry.output_snapshot) if log_entry.output_snapshot else None,
            "execution_time_ms": log_entry.execution_time_ms,
            "status": log_entry.status,
            "created_at": log_entry.created_at.isoformat()
        }
    
    finally:
        db.close()

def get_calculation_history(client_id: int = None, function_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get calculation history with optional filters
    """
    
    db = SessionLocal()
    try:
        query = db.query(CalculationLog)
        
        if client_id:
            query = query.filter(CalculationLog.client_id == client_id)
        
        if function_name:
            query = query.filter(CalculationLog.function_name == function_name)
        
        logs = query.order_by(CalculationLog.created_at.desc()).limit(limit).all()
        
        return [
            {
                "id": log.id,
                "trace_id": log.trace_id,
                "client_id": log.client_id,
                "function_name": log.function_name,
                "status": log.status,
                "execution_time_ms": log.execution_time_ms,
                "created_at": log.created_at.isoformat(),
                "error_message": log.error_message
            }
            for log in logs
        ]
    
    finally:
        db.close()
