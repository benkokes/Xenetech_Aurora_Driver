// Exact local printer DEVMODE backup/restore for the owned Aurora test queue.
// No document submission, receiver or device connection is implemented.
using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Web.Script.Serialization;

public static class PrinterModeBackup
{
    const string Name="Aurora JobServer (Test Capture)";
    [StructLayout(LayoutKind.Sequential)]struct Defaults {public IntPtr DataType,DevMode;public uint Access;}
    [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool OpenPrinter(string name,out IntPtr handle,ref Defaults defaults);
    [DllImport("winspool.drv",SetLastError=true)]static extern bool ClosePrinter(IntPtr handle);
    [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool GetPrinter(IntPtr handle,uint level,IntPtr data,uint size,out uint needed);
    [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool SetPrinter(IntPtr handle,uint level,ref IntPtr mode,uint command);
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    static string Hash(byte[] data){using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
    static byte[] Read(IntPtr handle,uint level)
    {
        uint needed;GetPrinter(handle,level,IntPtr.Zero,0,out needed);
        if(needed<IntPtr.Size || needed>1024*1024)throw new Win32Exception();
        IntPtr data=Marshal.AllocHGlobal((int)needed);
        try{
            if(!GetPrinter(handle,level,data,needed,out needed))throw new Win32Exception();
            IntPtr mode=Marshal.ReadIntPtr(data);if(mode==IntPtr.Zero)return null;
            int size=(ushort)Marshal.ReadInt16(mode,68),extra=(ushort)Marshal.ReadInt16(mode,70);
            if(size!=220 || size+extra>1024*1024)throw new Exception("Unexpected DEVMODE layout.");
            byte[] result=new byte[size+extra];Marshal.Copy(mode,result,0,result.Length);
            if(System.Text.Encoding.Unicode.GetString(result,0,64).TrimEnd('\0')!=Name)throw new Exception("Unexpected DEVMODE printer identity.");
            return result;
        }finally{Marshal.FreeHGlobal(data);}
    }
    static void Restore(IntPtr handle,uint level,byte[] bytes)
    {
        IntPtr mode=bytes==null?IntPtr.Zero:Marshal.AllocHGlobal(bytes.Length);
        try{
            if(bytes!=null)Marshal.Copy(bytes,0,mode,bytes.Length);
            if(!SetPrinter(handle,level,ref mode,0))throw new Win32Exception();
            byte[] actual=Read(handle,level);
            if((actual==null)!=(bytes==null) || (actual!=null && Hash(actual)!=Hash(bytes)))throw new Exception("Exact DEVMODE restoration differs; preserve backup.");
        }finally{if(mode!=IntPtr.Zero)Marshal.FreeHGlobal(mode);}
    }
    public static int Main(string[] args)
    {
        if(args.Length!=2)return 2;
        IntPtr handle=IntPtr.Zero;
        try{
            string action=args[0],folder=Path.GetFullPath(args[1]);
            if(action!="backup" && action!="restore-global" && action!="restore-user")throw new Exception("Unknown operation.");
            var defaults=new Defaults{Access=action=="restore-global"?12U:8U};
            if(!OpenPrinter(Name,out handle,ref defaults))throw new Win32Exception();
            if(action=="backup"){
                if(Directory.Exists(folder))throw new Exception("Preserve earlier backup; choose a fresh folder.");
                byte[] global=Read(handle,8),user=Read(handle,9);Directory.CreateDirectory(folder);
                var report=new Dictionary<string,object>{{"printer",Name},{"user",WindowsIdentity.GetCurrent().Name},{"schema_version",1}};
                foreach(var item in new[]{new KeyValuePair<string,byte[]>("global",global),new KeyValuePair<string,byte[]>("user",user)}){
                    report[item.Key+"_sha256"]=item.Value==null?null:Hash(item.Value);
                    if(item.Value!=null)File.WriteAllBytes(Path.Combine(folder,item.Key+".bin"),item.Value);
                }
                File.WriteAllText(Path.Combine(folder,"backup.json"),Json.Serialize(report));
            }else{
                var report=Json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(folder,"backup.json")));
                if((string)report["printer"]!=Name || Convert.ToInt32(report["schema_version"])!=1)throw new Exception("Backup identity changed.");
                string which=action=="restore-global"?"global":"user";
                if(which=="user" && (string)report["user"]!=WindowsIdentity.GetCurrent().Name)throw new Exception("Restore the user snapshot from its original Windows account.");
                string hash=(string)report[which+"_sha256"];
                byte[] bytes=hash==null?null:File.ReadAllBytes(Path.Combine(folder,which+".bin"));
                if(bytes!=null && Hash(bytes)!=hash)throw new Exception("Backup integrity failed.");
                Restore(handle,which=="global"?8U:9U,bytes);
            }
            Console.WriteLine(action+" passed; no document was printed.");return 0;
        }catch(Exception error){Console.Error.WriteLine(error);return 1;}
        finally{if(handle!=IntPtr.Zero)ClosePrinter(handle);}
    }
}
