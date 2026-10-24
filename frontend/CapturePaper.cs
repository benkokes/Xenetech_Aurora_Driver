using System;
using System.ComponentModel;
using System.Drawing.Printing;
using System.IO;
using System.Runtime.InteropServices;

namespace Aurora.Frontend
{
    // Win32 public DEVMODE complements the PrintTicket interface used
    // by modern print paths. All mutation is restricted to our capture queue.
    internal static class CapturePaper
    {
        internal const string Printer = "Aurora Capture (Preview Only)";
        [StructLayout(LayoutKind.Sequential)] struct Defaults { public IntPtr DataType, DevMode; public uint Access; }
        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool OpenPrinter(string name, out IntPtr printer, ref Defaults defaults);
        [DllImport("winspool.drv", SetLastError = true)] static extern bool ClosePrinter(IntPtr printer);
        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern int DocumentProperties(IntPtr window, IntPtr printer, string name, IntPtr output, IntPtr input, uint mode);
        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool SetPrinter(IntPtr printer, uint level, ref IntPtr devmode, uint command);
        [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool GetPrinter(IntPtr printer, uint level, IntPtr buffer, uint size, out uint needed);

        static IntPtr Open(bool administer)
        {
            IntPtr handle;
            Defaults defaults = new Defaults { Access = administer ? 12U : 8U };
            if (!OpenPrinter(Printer, out handle, ref defaults)) throw new Win32Exception(Marshal.GetLastWin32Error());
            return handle;
        }
        static IntPtr DefaultMode(IntPtr printer)
        {
            int bytes = DocumentProperties(IntPtr.Zero, printer, Printer, IntPtr.Zero, IntPtr.Zero, 0);
            if (bytes < 220 || bytes > 1024 * 1024) throw new InvalidOperationException("Invalid driver DEVMODE length.");
            IntPtr buffer = Marshal.AllocHGlobal(bytes);
            if (DocumentProperties(IntPtr.Zero, printer, Printer, buffer, IntPtr.Zero, 2) != 1)
            { Marshal.FreeHGlobal(buffer); throw new InvalidOperationException("Could not read default DEVMODE."); }
            return buffer;
        }
        static byte[] ModeBytes(IntPtr mode)
        {
            int size = (ushort)Marshal.ReadInt16(mode, 68), extra = (ushort)Marshal.ReadInt16(mode, 70);
            if (size < 166 || size + extra > 1024 * 1024) throw new InvalidOperationException("Invalid public DEVMODE layout.");
            byte[] bytes = new byte[size + extra]; Marshal.Copy(mode, bytes, 0, bytes.Length); return bytes;
        }
        static byte[] ReadStored(IntPtr printer, uint level)
        {
            uint needed; GetPrinter(printer, level, IntPtr.Zero, 0, out needed);
            if (needed < IntPtr.Size || needed > 1024 * 1024) throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr buffer = Marshal.AllocHGlobal((int)needed);
            try
            {
                if (!GetPrinter(printer, level, buffer, needed, out needed)) throw new Win32Exception(Marshal.GetLastWin32Error());
                IntPtr mode = Marshal.ReadIntPtr(buffer);
                return mode == IntPtr.Zero ? null : ModeBytes(mode);
            }
            finally { Marshal.FreeHGlobal(buffer); }
        }
        static void Store(IntPtr printer, uint level, byte[] bytes)
        {
            IntPtr mode = bytes == null ? IntPtr.Zero : Marshal.AllocHGlobal(bytes.Length);
            try
            {
                if (bytes != null) Marshal.Copy(bytes, 0, mode, bytes.Length);
                if (!SetPrinter(printer, level, ref mode, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
            }
            finally { if (mode != IntPtr.Zero) Marshal.FreeHGlobal(mode); }
        }
        static void Describe(IntPtr mode)
        {
            ModeBytes(mode);
            Console.WriteLine("Native DEVMODE: paper={0}, width={1}, length={2} (0.1 mm), orientation={3}, flags=0x{4:x}, form={5}",
                Marshal.ReadInt16(mode, 78), Marshal.ReadInt16(mode, 82), Marshal.ReadInt16(mode, 80), Marshal.ReadInt16(mode, 76),
                Marshal.ReadInt32(mode, 72), Marshal.PtrToStringUni(IntPtr.Add(mode, 102), 32).TrimEnd('\0'));
        }
        internal static void Inspect()
        {
            IntPtr handle = Open(false), mode = IntPtr.Zero;
            try { mode = DefaultMode(handle); Describe(mode); }
            finally { if (mode != IntPtr.Zero) Marshal.FreeHGlobal(mode); ClosePrinter(handle); }
        }
        internal static void Apply(string directory)
        {
            IntPtr handle = Open(true), mode = IntPtr.Zero;
            try
            {
                byte[] originalDefault = ReadStored(handle, 8), originalUser = ReadStored(handle, 9);
                if (originalDefault != null) File.WriteAllBytes(Path.Combine(directory, "global-devmode-before.bin"), originalDefault);
                if (originalUser != null) File.WriteAllBytes(Path.Combine(directory, "user-devmode-before.bin"), originalUser);
                mode = DefaultMode(handle);
                int fields = Marshal.ReadInt32(mode, 72);
                // Explicit width/length must win over a stale generic paper ID
                // or form name. PrintTicket-only updates left paper ID 256 set,
                // which legacy clients resolved to the generic Letter entry.
                fields = (fields | 1 | 4 | 8) & ~(2 | 0x10000);
                Marshal.WriteInt32(mode, 72, fields);
                Marshal.WriteInt16(mode, 76, 1); // Portrait, on the wide custom form.
                Marshal.WriteInt16(mode, 78, 0); // Custom dimensions, not the stale generic form 256.
                Marshal.WriteInt16(mode, 80, 4572);
                Marshal.WriteInt16(mode, 82, 7620);
                if (DocumentProperties(IntPtr.Zero, handle, Printer, mode, mode, 10) != 1)
                    throw new InvalidOperationException("The driver rejected the explicit custom Aurora DEVMODE.");
                Describe(mode);
                byte[] validated = ModeBytes(mode);
                File.WriteAllBytes(Path.Combine(directory, "custom-devmode-validated.bin"), validated);
                try
                {
                    Store(handle, 8, validated); Store(handle, 9, validated);
                    PrinterSettings settings = new PrinterSettings { PrinterName = Printer };
                    PaperSize paper = settings.DefaultPageSettings.PaperSize;
                    if (paper.Width != 3000 || paper.Height != 1800 || settings.DefaultPageSettings.Landscape)
                        throw new InvalidOperationException("GDI still does not expose a 30 x 18 inch paper size.");
                    Console.WriteLine("GDI confirmed: {0}, {1} x {2} hundredths of an inch.", paper.PaperName, paper.Width, paper.Height);
                }
                catch { Store(handle, 8, originalDefault); Store(handle, 9, originalUser); throw; }
            }
            finally { if (mode != IntPtr.Zero) Marshal.FreeHGlobal(mode); ClosePrinter(handle); }
        }
    }
}
