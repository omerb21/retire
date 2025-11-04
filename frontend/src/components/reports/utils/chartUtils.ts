import jsPDF from 'jspdf';

// ======= פונקציה להוספת גרף עוגה ל-PDF =======
export function drawPieChart(
  doc: jsPDF,
  x: number,
  y: number,
  radius: number,
  data: { labels: string[]; values: number[] }
): void {
  const total = data.values.reduce((sum, val) => sum + val, 0);
  
  if (total === 0) return;
  
  const colors = [
    [54, 162, 235],   // כחול
    [255, 99, 132],   // אדום
    [255, 206, 86],   // צהוב
    [75, 192, 192],   // ירוק-כחול
    [153, 102, 255],  // סגול
    [255, 159, 64],   // כתום
    [201, 203, 207]   // אפור
  ];
  
  let currentAngle = -Math.PI / 2; // מתחילים מלמעלה (12 שעות)
  
  // ציור העיגול החיצוני
  doc.setDrawColor(200, 200, 200);
  doc.setLineWidth(0.5);
  doc.circle(x, y, radius, 'S');
  
  // ציור הפלחים
  data.values.forEach((value, index) => {
    const sliceAngle = (value / total) * 2 * Math.PI;
    const endAngle = currentAngle + sliceAngle;
    const midAngle = currentAngle + sliceAngle / 2;
    
    // צבע הפלח
    const color = colors[index % colors.length];
    doc.setFillColor(color[0], color[1], color[2]);
    doc.setDrawColor(255, 255, 255);
    doc.setLineWidth(1);
    
    // נקודות הפלח
    const points: number[][] = [[x, y]];
    const steps = Math.max(10, Math.ceil(sliceAngle * 20)); // יותר נקודות לפלחים גדולים
    
    for (let i = 0; i <= steps; i++) {
      const angle = currentAngle + (sliceAngle * i / steps);
      const px = x + Math.cos(angle) * radius;
      const py = y + Math.sin(angle) * radius;
      points.push([px, py]);
    }
    
    // ציור הפלח כמצולע
    if (points.length >= 3) {
      doc.lines(
        points.slice(1).map((p, i) => {
          const prev = i === 0 ? points[0] : points[i];
          return [p[0] - prev[0], p[1] - prev[1]];
        }),
        points[0][0],
        points[0][1],
        [1, 1],
        'FD'
      );
    }
    
    // טקסט אחוזים על הפלח (רק לפלחים גדולים)
    const percentage = (value / total) * 100;
    if (percentage > 5) {
      const labelX = x + Math.cos(midAngle) * (radius * 0.65);
      const labelY = y + Math.sin(midAngle) * (radius * 0.65);
      doc.setFontSize(8);
      doc.setTextColor(255, 255, 255);
      doc.text(`${percentage.toFixed(0)}%`, labelX, labelY, { align: 'center' });
    }
    
    currentAngle = endAngle;
  });
  
  // הוספת לגנדה
  let legendY = y + radius + 20;
  const legendX = x - radius;
  
  doc.setFontSize(10);
  doc.setTextColor(0, 0, 0);
  doc.text('פילוח לפי סוג מוצר:', legendX, legendY - 10);
  
  data.labels.forEach((label, index) => {
    const color = colors[index % colors.length];
    const percentage = ((data.values[index] / total) * 100).toFixed(1);
    const value = data.values[index];
    
    // ריבוע צבע
    doc.setFillColor(color[0], color[1], color[2]);
    doc.setDrawColor(0, 0, 0);
    doc.setLineWidth(0.5);
    doc.rect(legendX, legendY - 3, 4, 4, 'FD');
    
    // טקסט
    doc.setFontSize(8);
    doc.setTextColor(0, 0, 0);
    const text = `${label}: ${percentage}% (₪${value.toLocaleString()})`;
    doc.text(text, legendX + 6, legendY);
    
    legendY += 6;
  });
}
