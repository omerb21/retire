"""Base calculator class for capital asset calculations."""

from abc import ABC, abstractmethod
from typing import Any


class BaseCalculator(ABC):
    """
    מחלקת בסיס אבסטרקטית לכל מחשבוני נכסי ההון.
    
    מגדירה ממשק משותף לכל סוגי החישובים:
    - הצמדה
    - מס
    - תשלומים
    - תזרים מזומנים
    
    כל מחלקה יורשת חייבת לממש את המתודה calculate().
    """
    
    @abstractmethod
    def calculate(self, *args, **kwargs) -> Any:
        """
        בצע את החישוב.
        
        Args:
            *args: פרמטרים משתנים לפי סוג החישוב
            **kwargs: פרמטרים בשם לפי סוג החישוב
            
        Returns:
            תוצאת החישוב (סוג משתנה לפי המימוש)
            
        Raises:
            NotImplementedError: אם המתודה לא מומשה במחלקה היורשת
        """
        raise NotImplementedError("Subclasses must implement calculate()")
    
    def validate_inputs(self, *args, **kwargs) -> None:
        """
        אמת את הקלט לפני ביצוע החישוב.
        
        מתודה זו ניתנת לעקיפה במחלקות יורשות.
        ברירת המחדל: לא עושה כלום.
        
        Args:
            *args: פרמטרים לאימות
            **kwargs: פרמטרים בשם לאימות
            
        Raises:
            ValueError: אם הקלט לא תקין
        """
        pass
