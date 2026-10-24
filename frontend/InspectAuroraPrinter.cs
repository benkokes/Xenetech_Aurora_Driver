using System;
using System.Drawing.Printing;
using System.IO;
using System.Printing;
using System.Web.Script.Serialization;

namespace Aurora.Frontend
{
    public static class InspectAuroraPrinter
    {
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if (args.Length != 1) throw new ArgumentException("Expected a new inspection directory.");
                string output = Path.GetFullPath(args[0]);
                if (Directory.Exists(output) || File.Exists(output)) throw new IOException("Inspection directory already exists.");
                const string name = "Aurora JobServer (Test Capture)";
                using (LocalPrintServer server = new LocalPrintServer())
                using (PrintQueue queue = server.GetPrintQueue(name))
                {
                    if (queue.QueueDriver.Name != "Aurora JobServer XPS Bridge" || queue.QueuePort.Name != "AuroraDirect_LPR_Loopback")
                        throw new InvalidOperationException("Unexpected test printer configuration.");
                    Directory.CreateDirectory(output);
                    using (Stream source = queue.DefaultPrintTicket.GetXmlStream())
                    using (Stream target = File.Create(Path.Combine(output,"default-printticket.xml"))) source.CopyTo(target);
                    PrintTicket user = queue.UserPrintTicket;
                    if (user != null)
                        using (Stream source = user.GetXmlStream())
                        using (Stream target = File.Create(Path.Combine(output,"user-printticket.xml"))) source.CopyTo(target);
                    using (Stream source = queue.GetPrintCapabilitiesAsXml())
                    using (Stream target = File.Create(Path.Combine(output,"printcapabilities.xml"))) source.CopyTo(target);
                    PrinterSettings settings = new PrinterSettings { PrinterName = name };
                    PageSettings page = settings.DefaultPageSettings;
                    string report = new JavaScriptSerializer().Serialize(new {
                        printer=name,driver=queue.QueueDriver.Name,port=queue.QueuePort.Name,
                        paper=page.PaperSize.PaperName,width_hundredths_inch=page.PaperSize.Width,
                        height_hundredths_inch=page.PaperSize.Height,landscape=page.Landscape,
                        source_dpi_x=page.PrinterResolution.X,source_dpi_y=page.PrinterResolution.Y,
                        printable_width_hundredths_inch=page.PrintableArea.Width,
                        printable_height_hundredths_inch=page.PrintableArea.Height,
                        device_io_performed=false });
                    File.WriteAllText(Path.Combine(output,"inspection.json"),report);
                    Console.WriteLine(report);
                }
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
