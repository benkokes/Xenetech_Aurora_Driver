// Minimal calls into Windows' native XPS OM. Interface slots and GUIDs are
// defined in Microsoft's xpsobjectmodel.h and xpsobjectmodel_1.h SDK headers:
// https://github.com/microsoft/win32metadata/tree/main/generation/WinSDK/RecompiledIdlHeaders/um
// No vendor code, namespace rewriting, external converter or raster fallback.
using System;
using System.IO;
using System.Runtime.InteropServices;

namespace Aurora.Frontend
{
    internal static class NativeXps
    {
        internal const int MicrosoftXps = 2, OpenXps = 3;
        static readonly Guid FactoryClass = new Guid("E974D26D-3D9B-4D47-88CC-3872F2DC3585");
        static readonly Guid Factory1Interface = new Guid("0a91b617-d612-4181-bf7c-be5824e9cc8f");

        [DllImport("ole32.dll")] static extern int CoInitializeEx(IntPtr reserved, uint flags);
        [DllImport("ole32.dll")] static extern void CoUninitialize();
        [DllImport("ole32.dll")] static extern int CoCreateInstance(ref Guid clsid, IntPtr outer, uint context, ref Guid iid, out IntPtr value);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int GetTypeFromFile(IntPtr self, [MarshalAs(UnmanagedType.LPWStr)] string path, out int type);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int PackageFromFile(IntPtr self, [MarshalAs(UnmanagedType.LPWStr)] string path, [MarshalAs(UnmanagedType.Bool)] bool reuse, out IntPtr package);
        [UnmanagedFunctionPointer(CallingConvention.StdCall)]
        delegate int WriteFile(IntPtr self, [MarshalAs(UnmanagedType.LPWStr)] string path, IntPtr security, uint flags,
                               [MarshalAs(UnmanagedType.Bool)] bool optimize, int type);

        // COM interface vtables are stable across Windows releases. Use only
        // these explicitly typed SDK methods; all HRESULTs and references are
        // checked/released. Slot numbers include the three IUnknown methods.
        static T Method<T>(IntPtr instance, int slot) where T : class
        {
            IntPtr table = Marshal.ReadIntPtr(instance);
            return (T)(object)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(table, slot * IntPtr.Size), typeof(T));
        }

        internal static int Convert(string source, string destination, int outputType)
        {
            if (outputType != MicrosoftXps && outputType != OpenXps) throw new ArgumentException("Unsupported XPS output type.");
            if (destination != null && (File.Exists(destination) || Directory.Exists(destination))) throw new IOException("XPS conversion output already exists.");
            int initialized = CoInitializeEx(IntPtr.Zero, 2); // COINIT_APARTMENTTHREADED
            Marshal.ThrowExceptionForHR(initialized);
            IntPtr factory = IntPtr.Zero, package = IntPtr.Zero;
            try
            {
                Guid clsid = FactoryClass, iid = Factory1Interface;
                Marshal.ThrowExceptionForHR(CoCreateInstance(ref clsid, IntPtr.Zero, 1, ref iid, out factory));
                int sourceType;
                Marshal.ThrowExceptionForHR(Method<GetTypeFromFile>(factory, 40)(factory, Path.GetFullPath(source), out sourceType));
                if (sourceType != MicrosoftXps && sourceType != OpenXps) throw new NotSupportedException("Input is not an XPS or OpenXPS document.");
                if (destination != null)
                {
                    Marshal.ThrowExceptionForHR(Method<PackageFromFile>(factory, 48)(factory, Path.GetFullPath(source), false, out package));
                    Marshal.ThrowExceptionForHR(Method<WriteFile>(package, 14)(package, Path.GetFullPath(destination), IntPtr.Zero, 0x80, false, outputType));
                }
                return sourceType;
            }
            finally
            {
                if (package != IntPtr.Zero) Marshal.Release(package);
                if (factory != IntPtr.Zero) Marshal.Release(factory);
                CoUninitialize();
            }
        }
    }
}
