// Generates one synthetic GDI print only to the exact local capture queue.
using System;
using System.Drawing;
using System.Drawing.Printing;
using System.Printing;

namespace Aurora.Frontend
{
    public static class PrintCaptureProbe
    {
        [STAThread]
        public static int Main()
        {
            const string name = "Aurora Capture (Preview Only)";
            try
            {
                using (LocalPrintServer server = new LocalPrintServer())
                using (PrintQueue queue = server.GetPrintQueue(name))
                {
                    if (queue.QueueDriver.Name != "Microsoft XPS Document Writer v4" || queue.QueuePort.Name != "AuroraCapture_LPR_Loopback")
                        throw new InvalidOperationException("Capture queue configuration does not match.");
                }
                using (PrintDocument document = new PrintDocument())
                {
                    document.PrinterSettings.PrinterName = name;
                    if (!document.PrinterSettings.IsValid) throw new InvalidOperationException("Capture printer is unavailable.");
                    document.DocumentName = "Aurora local GDI capture probe " + Guid.NewGuid().ToString("N");
                    document.PrintController = new StandardPrintController();
                    document.DefaultPageSettings.Margins = new Margins(0, 0, 0, 0);
                    document.DefaultPageSettings.Color = true;
                    document.PrintPage += delegate(object sender, PrintPageEventArgs e) {
                        e.Graphics.PageUnit = GraphicsUnit.Inch;
                        using (Pen pen = new Pen(Color.Red, 0.001f)) e.Graphics.DrawRectangle(pen, 0.25f, 0.25f, 1, 1);
                        e.Graphics.FillRectangle(Brushes.Black, 0.5f, 0.5f, 0.25f, 0.25f);
                        using (Font font = new Font("Arial", 12)) e.Graphics.DrawString("Aurora local capture", font, Brushes.Black, 0.25f, 1.5f);
                        e.HasMorePages = false;
                    };
                    document.Print();
                    Console.WriteLine("Submitted synthetic GDI page: " + document.DocumentName);
                }
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
