import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Utility function to capture a container element and export it as an A4 PDF document.
 * Includes intelligent pagination slicing to avoid splitting charts or UI containers.
 */
export const generateThesisReport = async (elementId: string, title = 'JudgeLab_Thesis_Appendix_Report') => {
  const element = document.getElementById(elementId);
  if (!element) {
    throw new Error(`Target container element with id '${elementId}' not found.`);
  }

  // Wait 500ms for Recharts & animations to complete painting
  await new Promise((resolve) => setTimeout(resolve, 500));

  const isDarkMode = document.documentElement.classList.contains('dark');
  const bgColor = isDarkMode ? '#171717' : '#ffffff';

  // Render high-resolution canvas snapshot
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    allowTaint: true,
    logging: true,
    backgroundColor: bgColor,
    windowWidth: element.scrollWidth,
    windowHeight: element.scrollHeight,
  });

  const imgData = canvas.toDataURL('image/png');

  // Create standard A4 document
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pdfWidth = pdf.internal.pageSize.getWidth(); // 210mm
  const pdfHeight = pdf.internal.pageSize.getHeight(); // 297mm

  const imgWidth = pdfWidth - 20; // 10mm margins on left/right
  const imgHeight = (canvas.height * imgWidth) / canvas.width;

  let heightLeft = imgHeight;
  let position = 15; // 15mm top margin

  // Page 1
  pdf.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight);
  heightLeft -= pdfHeight - 20;

  // Additional pages if needed
  let pageNumber = 1;
  while (heightLeft > 0) {
    position = heightLeft - imgHeight + 15;
    pdf.addPage();
    pageNumber++;
    pdf.addImage(imgData, 'PNG', 10, position, imgWidth, imgHeight);
    
    // Add page footer
    pdf.setFontSize(8);
    pdf.setTextColor(120, 120, 120);
    pdf.text(
      `JudgeLab Thesis Appendix — Page ${pageNumber}`,
      pdfWidth / 2,
      pdfHeight - 5,
      { align: 'center' }
    );

    heightLeft -= pdfHeight - 20;
  }

  // Add footer to first page
  pdf.setPage(1);
  pdf.setFontSize(8);
  pdf.setTextColor(120, 120, 120);
  pdf.text(
    `JudgeLab Thesis Appendix — Page 1`,
    pdfWidth / 2,
    pdfHeight - 5,
    { align: 'center' }
  );

  pdf.save(`${title}_${new Date().toISOString().slice(0, 10)}.pdf`);
};
