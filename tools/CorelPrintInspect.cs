using System;
using System.Runtime.InteropServices;
using VG=Corel.Interop.VGCore;

public static class CorelPrintInspect
{
    [STAThread]
    public static int Main()
    {
        try
        {
            VG.Application app=(VG.Application)Activator.CreateInstance(Type.GetTypeFromProgID("CorelDRAW.Application.17",true));
            VG.Document doc=app.ActiveDocument;
            if(doc==null) throw new Exception("No active document; nothing printed.");
            VG.PrintSettings ps=doc.PrintSettings;
            Console.WriteLine("Printer={0}; Paper={1}x{2}; PageMatching={3}; Placement={4}; Copies={5}; PrintToFile={6}",
                ps.Printer.Name,ps.PaperWidth,ps.PaperHeight,ps.PageMatchingMode,ps.Layout.Placement,ps.Copies,ps.PrintToFile);
            Console.WriteLine("ColorMode={0}; Profiles={1}; RasterizePage={2}; PrintVectors={3}; PrintBitmaps={4}; PrintText={5}",
                ps.Options.ColorMode,ps.Options.UseColorProfile,ps.Options.RasterizePage,
                ps.Options.PrintVectors,ps.Options.PrintBitmaps,ps.Options.PrintText);
            Console.WriteLine("Read-only inspection; no print submitted.");
            return 0;
        }
        catch(Exception ex){Console.Error.WriteLine(ex);return 1;}
    }
}
