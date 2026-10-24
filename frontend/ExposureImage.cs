using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Windows;
using System.Windows.Media.Imaging;

namespace Aurora.Frontend
{
    public sealed class ExposureReport
    {
        public string file, sha256;
        public string encoding = "exposure-u8-row-major";
        public string luminance = "(77R+150G+29B+128)>>8; exposure=255-luminance";
        public int width, height, x_pixels, y_pixels;
        public long colored_pixels;
    }
    internal static class ExposureImage
    {
        internal static ExposureReport Write(BitmapSource bitmap, string directory, int number, string fileName = null)
        {
            int width = bitmap.PixelWidth, height = bitmap.PixelHeight;
            byte[] exposure = new byte[width * height], row = new byte[width * 4];
            int left = width, top = height, right = -1, bottom = -1;
            long colored = 0;
            for (int y = 0; y < height; y++)
            {
                bitmap.CopyPixels(new Int32Rect(0, y, width, 1), row, row.Length, 0);
                for (int x = 0; x < width; x++)
                {
                    int i = x * 4;
                    if (row[i + 3] != 255) throw new InvalidOperationException("Exposure rendering must be opaque.");
                    if (row[i] != row[i + 1] || row[i] != row[i + 2]) colored++;
                    byte signal = (byte)(255 - ((77 * row[i + 2] + 150 * row[i + 1] + 29 * row[i] + 128) >> 8));
                    exposure[y * width + x] = signal;
                    if (signal == 0) continue;
                    left = Math.Min(left, x); right = Math.Max(right, x);
                    top = Math.Min(top, y); bottom = Math.Max(bottom, y);
                }
            }
            if (right < left) return null;
            ExposureReport report = new ExposureReport { width = right - left + 1, height = bottom - top + 1,
                x_pixels = left, y_pixels = top, colored_pixels = colored,
                file = fileName ?? String.Format(CultureInfo.InvariantCulture, "page-{0:000}-exposure.bin", number) };
            if(Path.GetFileName(report.file)!=report.file)throw new ArgumentException("Expected a local exposure filename.");
            byte[] cropped = new byte[report.width * report.height];
            for (int y = 0; y < report.height; y++) Buffer.BlockCopy(exposure, (y + top) * width + left, cropped, y * report.width, report.width);
            using (SHA256 hash = SHA256.Create()) report.sha256 = BitConverter.ToString(hash.ComputeHash(cropped)).Replace("-", "").ToLowerInvariant();
            using (FileStream file = new FileStream(Path.Combine(directory, report.file), FileMode.CreateNew)) file.Write(cropped, 0, cropped.Length);
            return report;
        }
    }
}
