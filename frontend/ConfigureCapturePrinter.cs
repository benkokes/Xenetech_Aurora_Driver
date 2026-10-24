using System;
using System.IO;
using System.Printing;

namespace Aurora.Frontend
{
    public static class ConfigureCapturePrinter
    {
        static void Save(PrintTicket ticket, string path)
        {
            using (FileStream file = new FileStream(path, FileMode.CreateNew)) ticket.SaveTo(file);
        }
        static void Describe(string label, PrintTicket ticket)
        {
            PageMediaSize size = ticket.PageMediaSize;
            Console.WriteLine("{0}: {1} x {2} DIP; {3}; scaling {4}", label,
                size == null ? null : size.Width, size == null ? null : size.Height,
                ticket.PageOrientation, ticket.PageScalingFactor);
        }
        static void CheckBed(PrintTicket ticket)
        {
            PageMediaSize size = ticket.PageMediaSize;
            if (size == null || !size.Width.HasValue || !size.Height.HasValue ||
                Math.Abs(size.Width.Value - 2880) > 0.1 || Math.Abs(size.Height.Value - 1728) > 0.1 ||
                ticket.PageOrientation != PageOrientation.Portrait)
                throw new InvalidOperationException("The driver did not retain a 30 x 18 inch bed without rotation.");
        }
        [STAThread]
        public static int Main(string[] args)
        {
            try
            {
                if (args.Length < 1 || args.Length > 2 || (args.Length == 2 && args[1] != "--apply"))
                    throw new ArgumentException("Usage: Aurora.ConfigureCapturePrinter.exe NEW-RECORD-DIRECTORY [--apply]");
                string directory = Path.GetFullPath(args[0]);
                if (Directory.Exists(directory) || File.Exists(directory)) throw new IOException("Record directory already exists.");
                Directory.CreateDirectory(directory);
                using (LocalPrintServer server = new LocalPrintServer())
                using (PrintQueue queue = new PrintQueue(server, "Aurora Capture (Preview Only)", PrintSystemDesiredAccess.AdministratePrinter))
                {
                    if (queue.QueueDriver.Name != "Microsoft XPS Document Writer v4" || queue.QueuePort.Name != "AuroraCapture_LPR_Loopback")
                        throw new InvalidOperationException("Capture queue configuration does not match.");
                    PrintTicket originalDefault = queue.DefaultPrintTicket, originalUser = queue.UserPrintTicket;
                    Save(originalDefault, Path.Combine(directory, "default-before.xml"));
                    Save(originalUser, Path.Combine(directory, "user-before.xml"));
                    using (Stream capabilities = queue.GetPrintCapabilitiesAsXml())
                    using (FileStream file = new FileStream(Path.Combine(directory, "capabilities-before.xml"), FileMode.CreateNew)) capabilities.CopyTo(file);
                    Describe("Before", originalUser);
                    PrintTicket delta = new PrintTicket { PageMediaSize = new PageMediaSize(2880, 1728),
                        PageOrientation = PageOrientation.Portrait, PageScalingFactor = 100 };
                    PrintTicket validatedDefault = queue.MergeAndValidatePrintTicket(originalDefault, delta).ValidatedPrintTicket;
                    PrintTicket validatedUser = queue.MergeAndValidatePrintTicket(originalUser, delta).ValidatedPrintTicket;
                    Save(validatedUser, Path.Combine(directory, "user-validated.xml"));
                    Describe("Validated", validatedUser);
                    CheckBed(validatedDefault); CheckBed(validatedUser);
                    if (args.Length == 1) { Console.WriteLine("Inspection only; queue settings were not changed."); return 0; }
                    try
                    {
                        queue.DefaultPrintTicket = validatedDefault;
                        queue.UserPrintTicket = validatedUser;
                        queue.Commit(); queue.Refresh();
                        CheckBed(queue.DefaultPrintTicket); CheckBed(queue.UserPrintTicket);
                        Save(queue.DefaultPrintTicket, Path.Combine(directory, "default-after.xml"));
                        Save(queue.UserPrintTicket, Path.Combine(directory, "user-after.xml"));
                        Describe("Applied", queue.UserPrintTicket);
                        CapturePaper.Apply(directory);
                    }
                    catch
                    {
                        queue.DefaultPrintTicket = originalDefault; queue.UserPrintTicket = originalUser; queue.Commit();
                        throw;
                    }
                }
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
