using System;
using System.Drawing.Printing;
using System.Printing;

namespace Aurora.Frontend
{
    public static class InspectCapturePrinter
    {
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                const string name = "Aurora Capture (Preview Only)";
                using (LocalPrintServer server = new LocalPrintServer())
                using (PrintQueue queue = server.GetPrintQueue(name))
                {
                    if (queue.QueueDriver.Name != "Microsoft XPS Document Writer v4" || queue.QueuePort.Name != "AuroraCapture_LPR_Loopback")
                        throw new InvalidOperationException("Capture queue configuration does not match.");
                }
                PrinterSettings settings = new PrinterSettings { PrinterName = name };
                CapturePaper.Inspect();
                PageSettings page = settings.DefaultPageSettings;
                PaperSize paper = page.PaperSize;
                Console.WriteLine("GDI default: {0}, {1} x {2} hundredths of an inch, raw kind {3}, landscape {4}", paper.PaperName, paper.Width, paper.Height, paper.RawKind, page.Landscape);
                Console.WriteLine("GDI printable area (hundredths of an inch): " + page.PrintableArea);
                if (args.Length > 0 && args[0] == "--forms")
                    foreach (PaperSize form in settings.PaperSizes)
                        Console.WriteLine("GDI form: {0}, {1} x {2}, raw kind {3}", form.PaperName, form.Width, form.Height, form.RawKind);
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
