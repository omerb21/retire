import React from 'react';
import { Card, CardContent, Typography, List, ListItem, ListItemText, Divider, Box } from '@mui/material';

const TaxCalculationDocumentation: React.FC = () => {
  return (
    <Box sx={{ maxWidth: 1200, margin: '0 auto', padding: 3 }}>
      <Card elevation={3}>
        <CardContent>
          <Typography variant="h4" gutterBottom>
            📊 לוגיקת חישובי מס במסך התוצאות
          </Typography>
          
          <Typography variant="h6" sx={{ mt: 3, mb: 2 }}>
            סוגי יחסי מס
          </Typography>
          <List>
            <ListItem>
              <ListItemText 
                primary="חייב במס (taxable)" 
                secondary="נכנס לחישוב המס הכללי לפי מדרגות המס. מחושב על פי מדרגות המס השנתיות הרלוונטיות לשנה הנבחרת."
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText 
                primary="פטור ממס (exempt)" 
                secondary="לא מחויב במס. ההכנסה אינה נכללת בחישוב המס."
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText 
                primary="מס רווח הון (capital_gains)" 
                secondary={
                  <span>
                    מחושב כ-25% מהרווח הריאלי (תשלום - צבירה מקורית).<br/>
                    <strong>חשוב:</strong> אם לא הוגדרה צבירה מקורית, ברירת המחדל היא ערך התשלום (אין רווח).
                  </span>
                }
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText 
                primary="שיעור מס קבוע (fixed_rate)" 
                secondary={
                  <span>
                    מחושב לפי אחוז המס שהוגדר (field: tax_rate).<br/>
                    <strong>נוסחה:</strong> תשלום * (tax_rate / 100)
                  </span>
                }
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText 
                primary="פריסת מס (tax_spread)" 
                secondary={
                  <span>
                    מחושב על ידי חלוקת התשלום למספר השנים שצוין (spread_years),<br/>
                    וחישוב מס נפרד לכל שנה לפי מדרגות המס.
                  </span>
                }
              />
            </ListItem>
          </List>

          <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
            נכסי הון
          </Typography>
          <Typography paragraph>
            נכסי הון יכולים להיות מסוגים שונים (קרן השתלמות, נדל"ן וכו') ולכל אחד מהם חישוב מס ייחודי:
          </Typography>
          <List>
            <ListItem>
              <ListItemText 
                primary='נדל"ן להשכרה'
                secondary='פטור ממס על 6,084 ש"ח הכנסה חודשית (72,000 ש"ח שנתי). מעל לסכום זה - מס רגיל לפי מדרגות.'
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText 
                primary="קרן השתלמות" 
                secondary="פטור ממס לאחר 6 שנים. לפני כן - מס רווח הון 25% על הרווח הריאלי."
              />
            </ListItem>
          </List>

          <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
            המרות פנסיה להון
          </Typography>
          <Typography paragraph>
            בעת המרת קרן פנסיה להון, נשמר יחס המס המקורי של הקרן:
          </Typography>
          <List>
            <ListItem>
              <ListItemText 
                primary="תגמולי עובד עד 2000" 
                secondary="אוטומטית מסומן כ'פטור ממס'"
              />
            </ListItem>
            <ListItem>
              <ListItemText 
                primary="תגמולי מעביד עד 2000" 
                secondary="אוטומטית מסומן כ'פטור ממס'"
              />
            </ListItem>
            <ListItem>
              <ListItemText 
                primary="סכומים אחרים" 
                secondary="מסומנים כ'חייב במס' כברירת מחדל, אלא אם שונה ידנית"
              />
            </ListItem>
          </List>

          <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
            הערות חשובות
          </Typography>
          <List>
            <ListItem>
              <ListItemText 
                primary="חישוב שנתי" 
                secondary="כל החישובים מבוצעים קודם לשנה שלמה, ולאחר מכן מחולקים ל-12 לחישוב חודשי"
              />
            </ListItem>
            <ListItem>
              <ListItemText 
                primary="עיגולים" 
                secondary="החישובים מעוגלים לשקל הקרוב בסוף התהליך"
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>
    </Box>
  );
};

export default TaxCalculationDocumentation;
