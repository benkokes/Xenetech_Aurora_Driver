using System;
using System.Reflection;
using System.Reflection.Emit;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

namespace Aurora.Frontend
{
    // Import Windows' installed printer-extension type library without an SDK
    // or downloaded executable. The generated assembly contains COM metadata.
    public sealed class BuildPrinterInterop : ITypeLibImporterNotifySink
    {
        [DllImport("oleaut32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
        static extern void LoadTypeLibEx(string path, int registrationKind, out ITypeLib library);

        public void ReportEvent(ImporterEventKind kind, int code, string message)
        { Console.WriteLine("{0}: {1}",kind,message); }

        public Assembly ResolveRef(object library)
        { throw new InvalidOperationException("Unexpected external printer type library dependency."); }

        public static int Main(string[] args)
        {
            try
            {
                if (args.Length != 2) throw new ArgumentException("Expected Windows type-library resource and output DLL.");
                ITypeLib library;
                LoadTypeLibEx(args[0],2,out library); // REGKIND_NONE: no COM registration.
                AssemblyBuilder assembly = new TypeLibConverter().ConvertTypeLibToAssembly(
                    library,args[1],TypeLibImporterFlags.SafeArrayAsSystemArray,
                    new BuildPrinterInterop(),null,null,"PrinterExtensionLib",null);
                assembly.Save(System.IO.Path.GetFileName(args[1]));
                Marshal.ReleaseComObject(library);
                return 0;
            }
            catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        }
    }
}
