using System;
using System.Runtime.InteropServices;
using System.Text;

namespace Aurora.Frontend
{
    public static class PrinterPackageInstall
    {
        const string PrinterLibrary = "winspool.drv";
        [DllImport(PrinterLibrary, CharSet=CharSet.Unicode, ExactSpelling=true)]
        static extern int UploadPrinterDriverPackageW(string server, string inf, string environment,
            uint flags, IntPtr window, StringBuilder destination, ref uint characters);
        [DllImport(PrinterLibrary, CharSet=CharSet.Unicode, ExactSpelling=true)]
        static extern int InstallPrinterDriverFromPackageW(string server, string inf, string name,
            string environment, uint flags);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        static extern IntPtr LoadLibraryEx(string name, IntPtr file, uint flags);
        [DllImport("kernel32.dll", CharSet=CharSet.Ansi, ExactSpelling=true)]
        static extern IntPtr GetProcAddress(IntPtr module, string name);
        [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
        public static int Main(string[] args)
        {
            try
            {
                if (args.Length == 1 && args[0] == "--check-api")
                {
                    IntPtr library = LoadLibraryEx(PrinterLibrary,IntPtr.Zero,0x800);
                    if (library == IntPtr.Zero) throw new InvalidOperationException("Windows printer library unavailable.");
                    try
                    {
                        foreach (string name in new[] { "UploadPrinterDriverPackageW", "InstallPrinterDriverFromPackageW" })
                            if (GetProcAddress(library,name) == IntPtr.Zero) throw new EntryPointNotFoundException(name);
                        Console.WriteLine("Printer package API entry points verified; no installation performed.");
                    }
                    finally { FreeLibrary(library); }
                    return 0;
                }
                if (args.Length != 2) throw new ArgumentException("Expected signed INF path and driver name.");
                uint size = 32768;
                StringBuilder path = new StringBuilder((int)size);
                Marshal.ThrowExceptionForHR(UploadPrinterDriverPackageW(null,args[0],"Windows x64",1,IntPtr.Zero,path,ref size));
                Marshal.ThrowExceptionForHR(InstallPrinterDriverFromPackageW(null,path.ToString(),args[1],"Windows x64",0));
                Console.WriteLine(path.ToString());
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine("{0} (HRESULT 0x{1:X8})",error.Message,error.HResult); return 1; }
        }
    }
}
