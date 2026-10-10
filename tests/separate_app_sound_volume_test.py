# SPDX-License-Identifier: Apache-2.0
"""Host regression for the production volume cache; never builds Android.

Compiles the real cache class with inert declarations for its two Android types.
This validates Java cache/concurrency behavior, not framework or HAL integration.
"""
from pathlib import Path
import os
TOOLS = Path(__file__).resolve().parents[1]
import shutil
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(os.environ.get('ROM_ROOT', '.')).resolve()
bundled = root / 'prebuilts/jdk/jdk21/linux-x86/bin'
javac = shutil.which('javac') or str(bundled / 'javac')
java = shutil.which('java') or str(bundled / 'java')
source = root / 'frameworks/base/services/core/java/com/android/server/audio/SeparateAppSoundVolumeState.java'

with tempfile.TemporaryDirectory(prefix='sas-volume-', dir='/tmp') as directory:
    work = Path(directory)
    def write(name, text):
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)

    files = [write('android/media/AudioDeviceAttributes.java',
                   'package android.media; public final class AudioDeviceAttributes {}'),
             write('android/media/AudioSystem.java',
                   'package android.media; public final class AudioSystem {'
                   ' public static final int MODE_NORMAL = 0; }'), str(source)]
    files.append(write('com/android/server/audio/VolumeRegression.java', r'''
package com.android.server.audio;
import android.media.AudioDeviceAttributes;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import javax.tools.*;
import com.sun.source.util.JavacTask;

public final class VolumeRegression {
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("volume regression");
    }
    public static void main(String[] args) throws Exception {
        // Parse Android integration sources without compiling or resolving their dependencies.
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, null, null)) {
            JavacTask task = (JavacTask) compiler.getTask(null, manager, diagnostics,
                    null, null, manager.getJavaFileObjects(args));
            task.parse();
            for (Diagnostic<?> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR)
                    throw new AssertionError(diagnostic.toString());
            }
        }
        AtomicInteger mode = new AtomicInteger(0);
        SeparateAppSoundVolumeState state = new SeparateAppSoundVolumeState(mode::get);
        AudioDeviceAttributes target = new AudioDeviceAttributes();
        check(state.get() == null);
        state.publish(state.snapshot(), target);

        // Reproduce the lock-order surroundings: broker owns the mode lock,
        // then waits for the volume lock. Lookup under volume lock must finish.
        Object modeLock = new Object(), volumeLock = new Object();
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch modeHeld = new CountDownLatch(1), volumeHeld = new CountDownLatch(1);
        try {
            Future<?> lookup = pool.submit(() -> {
                synchronized (volumeLock) {
                    volumeHeld.countDown();
                    try { check(modeHeld.await(2, TimeUnit.SECONDS)); }
                    catch (InterruptedException e) { throw new AssertionError(e); }
                    check(state.get() == target);
                }
            });
            check(volumeHeld.await(2, TimeUnit.SECONDS));
            Future<?> broker = pool.submit(() -> {
                synchronized (modeLock) {
                    modeHeld.countDown();
                    synchronized (volumeLock) {}
                }
            });
            lookup.get(3, TimeUnit.SECONDS);
            broker.get(3, TimeUnit.SECONDS);

            for (int m : new int[] {1, 2, 3, 4}) {
                mode.set(m); check(state.get() == null);
            }
            mode.set(0); check(state.get() == target);
            SeparateAppSoundVolumeState.Snapshot old = state.snapshot();
            state.clear(); state.publish(old, target); check(state.get() == null);
            state.publish(state.snapshot(), target);
            state.publish(old, null); check(state.get() == target);

            Set<Integer> selected = Set.of(10001);
            check(SeparateAppSoundVolumeState.select(target, selected, selected, selected) == target);
            check(SeparateAppSoundVolumeState.select(target, selected, Set.of(), selected) == null);
            check(SeparateAppSoundVolumeState.select(target, selected, selected, Set.of()) == null);
            check(SeparateAppSoundVolumeState.select(target, selected, Set.of(10002), Set.of(10002)) == null);
            // Stress invalidation versus publication: stale work must never win.
            for (int i = 0; i < 10000; i++) {
                SeparateAppSoundVolumeState.Snapshot token = state.snapshot();
                pool.submit(state::clear).get(2, TimeUnit.SECONDS);
                pool.submit(() -> state.publish(token, target)).get(2, TimeUnit.SECONDS);
                check(state.get() == null);
            }
            System.out.println("PASS: lock-order completion, mode gating, eligibility and stale-refresh rejection.");
        } finally {
            pool.shutdownNow();
            check(pool.awaitTermination(3, TimeUnit.SECONDS));
        }
    }
}
'''))
    subprocess.run([javac, '-d', str(work / 'classes'), *files], check=True, timeout=30)
    subprocess.run([java, '-cp', str(work / 'classes'),
                    'com.android.server.audio.VolumeRegression',
                    str(root / 'frameworks/base/services/core/java/com/android/server/audio/SeparateAppSoundController.java'),
                    str(root / 'frameworks/base/services/core/java/com/android/server/audio/AudioService.java'),
                    str(root / 'frameworks/base/packages/SystemUI/src/com/android/systemui/volume/VolumeDialogControllerImpl.java'),
                    str(root / 'frameworks/base/services/tests/audio/src/com/android/server/audio/SeparateAppSoundVolumeStateTest.java')],
                   check=True, timeout=30)
