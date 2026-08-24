// The Clear BSD License
//
// Copyright (c) 2026 Ian Hylton
// All rights reserved.


using System.Reflection;
using System.Runtime.CompilerServices;


namespace CmdRouter.Example.Utils;


public static class Path {
    [MethodImpl(MethodImplOptions.AggressiveInlining)]
    public static string Asm() => Assembly.GetExecutingAssembly().Location;

    public static void Print(params string?[ ] m) => Console.WriteLine(value:string.Join("> ", m));

    /// <summary>
    ///     Traverses upward from the executing assembly directory until a directory
    ///     containing <c> uv.lock </c> is found.
    ///     This equivalent to our Python implementation of `_Paths._get_root`.
    /// </summary>
    public static string ThisPath() {
        var asm = Asm();

        var current = !string.IsNullOrWhiteSpace(asm)
            ? new DirectoryInfo(path:System.IO.Path.GetDirectoryName(asm)!)
            : new DirectoryInfo(AppContext.BaseDirectory);

        while (current.Parent is not null) {
            if (File.Exists(path:System.IO.Path.Combine(current.FullName, "uv.lock"))) return current.FullName;
            current = current.Parent;
        }

        // Check the filesystem root as well.
        return File.Exists(path:System.IO.Path.Combine(current.FullName, "uv.lock"))
            ? current.FullName
            :
            // Equivalent to Python's Path.cwd().
            Directory.GetCurrentDirectory();
    }
}
