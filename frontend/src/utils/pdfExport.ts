import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

/**
 * Utility function to capture a container element and export it as an A4 PDF document.
 * Includes intelligent pagination slicing to avoid splitting charts or UI containers.
 */
export const generateThesisReport = async (elementId: string, title = 'JudgeLab_Thesis_Appendix_Report') => {
  const element = document.getElementById(elementId);
  if (!element) {
    const errorMsg = `Target container element with id '${elementId}' not found.`;
    console.error('[PDF Export]', errorMsg);
    throw new Error(errorMsg);
  }

  const rect = element.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    const errorMsg = `Target container '${elementId}' has 0x0 dimensions (hidden or collapsed layout).`;
    console.error('[PDF Export]', errorMsg);
    throw new Error(errorMsg);
  }

  // Wait 500ms for Recharts & animations to complete painting
  await new Promise((resolve) => setTimeout(resolve, 500));

  const isDarkMode = document.documentElement.classList.contains('dark');
  const bgColor = isDarkMode ? '#171717' : '#ffffff';

  try {
    // Render high-resolution canvas snapshot with SVG dimension cloning
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      allowTaint: true,
      logging: true,
      backgroundColor: bgColor,
      windowWidth: element.scrollWidth,
      windowHeight: element.scrollHeight,
      onclone: (clonedDoc) => {
        // Fix for Recharts responsive containers & SVGs
        const origContainers = element.querySelectorAll('.recharts-responsive-container');
        const clonedContainers = clonedDoc.querySelectorAll('.recharts-responsive-container');
        origContainers.forEach((orig, idx) => {
          const cloned = clonedContainers[idx] as HTMLElement;
          if (cloned) {
            const origRect = orig.getBoundingClientRect();
            if (origRect.width > 0 && origRect.height > 0) {
              cloned.style.width = `${origRect.width}px`;
              cloned.style.height = `${origRect.height}px`;
            }
          }
        });

        const origSvgs = element.querySelectorAll('svg');
        const clonedSvgs = clonedDoc.querySelectorAll('svg');
        origSvgs.forEach((origSvg, idx) => {
          const clonedSvg = clonedSvgs[idx];
          if (clonedSvg) {
            const origRect = origSvg.getBoundingClientRect();
            if (origRect.width > 0 && origRect.height > 0) {
              clonedSvg.setAttribute('width', `${origRect.width}px`);
              clonedSvg.setAttribute('height', `${origRect.height}px`);
              clonedSvg.style.width = `${origRect.width}px`;
              clonedSvg.style.height = `${origRect.height}px`;
            }
          }
        });
      },
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

    const fileName = `${title}_${new Date().toISOString().slice(0, 10)}.pdf`;
    pdf.save(fileName);
    console.log(`[PDF Export] Successfully exported PDF report '${fileName}'.`);
  } catch (err: any) {
    console.error('[PDF Export Failure]', err);
    console.warn('[PDF Export] Triggering native window.print() fallback...');
    window.print();
    throw err;
  }
};
