###############################################################################
#   actionAngle: a Python module to calculate  actions, angles, and frequencies
#
#      class: actionAngleVerticalInverse
#
#             Calculate (x,v) coordinates for a one-dimensional potental
#             given actions-angle coordinates
#
###############################################################################
import copy
import numpy
from galpy.potential import evaluatelinearPotentials, \
    evaluatelinearForces
from galpy.actionAngle import actionAngleHarmonic, actionAngleHarmonicInverse
from galpy.actionAngle_src.actionAngleVertical import actionAngleVertical
from galpy.actionAngle_src.actionAngleInverse import actionAngleInverse
class actionAngleVerticalInverse(actionAngleInverse):
    """Inverse action-angle formalism for one dimensional systems"""
    def __init__(self,Es=[0.1,0.3],pot=None,nta=128):
        """
        NAME:

           __init__

        PURPOSE:

           initialize an actionAngleVerticalInverse object

        INPUT:

           pot= a linearPotential or list thereof

        OUTPUT:

           instance

        HISTORY:

           2018-04-11 - Started - Bovy (UofT)

        """
        #actionAngleInverse.__init__(self,*args,**kwargs)
        if pot is None: #pragma: no cover
            raise IOError("Must specify pot= for actionAngleVerticalInverse")
        self._pot= pot
        self._aAV= actionAngleVertical(pot=self._pot)
        # Compute action, frequency, and xmax for each energy
        nE= len(Es)
        js= numpy.empty(nE)
        Omegas= numpy.empty(nE)
        xmaxs= numpy.empty(nE)
        for ii,E in enumerate(Es):
            tJ,tO= self._aAV.actionsFreqs(0.,\
                     numpy.sqrt(2.*(E-evaluatelinearPotentials(self._pot,0.))))
            js[ii]= tJ
            Omegas[ii]= tO
            xmaxs[ii]=\
               self._aAV.calcxmax(0.,numpy.sqrt(2.*(\
                             E-evaluatelinearPotentials(self._pot,0.))),
                           E=E)
        self._Es= numpy.array(Es)
        self._js= js
        self._Omegas= Omegas
        self._xmaxs= xmaxs
        # Set harmonic-oscillator frequencies == frequencies
        self._OmegaHO= Omegas
        # The following work properly for arrays of omega
        self._hoaa= actionAngleHarmonic(omega=self._OmegaHO)
        self._hoaainv= actionAngleHarmonicInverse(omega=self._OmegaHO)
        # Now map all tori
        self._nta= nta
        self._thetaa= numpy.linspace(0.,2.*numpy.pi*(1.-1./nta),nta)
        self._xgrid= self._create_xgrid()
        self._ja= _ja(self._xgrid,self._Egrid,self._pot,self._omegagrid)
        self._djadj= _djadj(self._xgrid,self._Egrid,self._pot,self._omegagrid)
        # Store mean(ja) as probably a better approx. of j
        self._js_orig= copy.copy(self._js)
        self._js= numpy.mean(self._ja,axis=1)
        # Compute Fourier expansions
        self._nforSn= numpy.arange(self._ja.shape[1]//2+1)
        self._nSn= numpy.real(numpy.fft.rfft(self._ja-numpy.atleast_2d(self._js).T,axis=1))[:,1:]/self._ja.shape[1]
        self._dSndJ= (numpy.real(numpy.fft.rfft(self._djadj-1.,axis=1))/numpy.atleast_2d(self._nforSn))[:,1:]/self._ja.shape[1]
        self._nforSn= self._nforSn[1:]
        return None

    def _create_xgrid(self):
        # Find x grid for regular grid in auxiliary angle (thetaa)
        # in practice only need to map 0 < thetaa < pi/2  to +x with +v bc symm
        # To efficiently start the search, we first compute thetaa for a dense
        # grid in x (at +v)
        xgrid= numpy.linspace(-1.,1.,2*self._nta)
        xs= xgrid*numpy.atleast_2d(self._xmaxs).T
        xta= _anglea(xs,numpy.tile(self._Es,(xs.shape[1],1)).T,
                     self._pot,numpy.tile(self._hoaa._omega,(xs.shape[1],1)).T)
        # Now use Newton-Raphson to iterate to a regular grid
        cindx= numpy.argmin(numpy.fabs(\
                (xta-numpy.rollaxis(numpy.atleast_3d(self._thetaa),1)
                 +numpy.pi) % (2.*numpy.pi)-numpy.pi),axis=2)
        xgrid= xgrid[cindx].T*numpy.atleast_2d(self._xmaxs).T
        Egrid= numpy.tile(self._Es,(self._nta,1)).T
        omegagrid= numpy.tile(self._hoaa._omega,(self._nta,1)).T
        xmaxgrid= numpy.tile(self._xmaxs,(self._nta,1)).T
        ta= _anglea(xgrid,Egrid,self._pot,omegagrid)
        mta= numpy.tile(self._thetaa,(len(self._Es),1))
        # Now iterate
        maxiter= 100
        tol= 1.e-12
        cntr= 0
        unconv= numpy.ones(xgrid.shape,dtype='bool')
        # We'll fill in the -v part using the +v, also remove the endpoints
        unconv[:,self._nta//4:3*self._nta//4+1]= False
        dta= (ta[unconv]-mta[unconv]+numpy.pi) % (2.*numpy.pi)-numpy.pi
        unconv[unconv]= numpy.fabs(dta) > tol
        # Don't allow too big steps
        maxdx= numpy.tile(self._xmaxs/float(self._nta),(self._nta,1)).T
        while True:
            dtadx= _danglea(xgrid[unconv],Egrid[unconv],
                            self._pot,omegagrid[unconv])
            dta= (ta[unconv]-mta[unconv]+numpy.pi) % (2.*numpy.pi)-numpy.pi
            dx= -dta/dtadx
            dx[numpy.fabs(dx) > maxdx[unconv]]= (numpy.sign(dx)*maxdx[unconv])[numpy.fabs(dx) > maxdx[unconv]]
            xgrid[unconv]+= dx
            xgrid[unconv*(xgrid > xmaxgrid)]= xmaxgrid[unconv*(xgrid > xmaxgrid)]
            xgrid[unconv*(xgrid < -xmaxgrid)]= xmaxgrid[unconv*(xgrid < -xmaxgrid)]
            unconv[unconv]= numpy.fabs(dta) > tol
            newta= _anglea(xgrid[unconv],Egrid[unconv],
                           self._pot,omegagrid[unconv])
            ta[unconv]= newta
            cntr+= 1
            if numpy.sum(unconv) == 0:
                print("Took %i iterations" % cntr)
                break
            if cntr > maxiter:
                print("WARNING: DIDN'T CONVERGE IN {} iterations".format(maxiter))
                break
                raise RuntimeError("Convergence of grid-finding not achieved in %i iterations" % maxiter)
        xgrid[:,self._nta//4+1:self._nta//2+1]= xgrid[:,:self._nta//4][:,::-1]
        xgrid[:,self._nta//2+1:3*self._nta//4+1]= xgrid[:,3*self._nta//4:][:,::-1]
        ta[:,self._nta//4+1:3*self._nta//4]= \
            _anglea(xgrid[:,self._nta//4+1:3*self._nta//4],
                    Egrid[:,self._nta//4+1:3*self._nta//4],
                    self._pot,
                    omegagrid[:,self._nta//4+1:3*self._nta//4],
                    vsign=-1.)
        self._dta= (ta-mta+numpy.pi) % (2.*numpy.pi)-numpy.pi
        self._mta= mta
        # Store these, they are useful (obv. arbitrary to return xgrid and not just store it...)
        self._Egrid= Egrid
        self._omegagrid= omegagrid
        self._xmaxgrid= xmaxgrid
        return xgrid

    def _evaluate(self,j,angle,**kwargs):
        """
        NAME:

           __call__

        PURPOSE:

           evaluate the phase-space coordinates (x,v) for a number of angles on a single torus

        INPUT:

           j - action (scalar)

           angle - angle (array [N])

        OUTPUT:

           [x,vx]

        HISTORY:

           2018-04-08 - Written - Bovy (UofT)

        """
        return self._xvFreqs(j,angle,**kwargs)[:2]
        
    def _xvFreqs(self,j,angle,**kwargs):
        """
        NAME:

           xvFreqs

        PURPOSE:

           evaluate the phase-space coordinates (x,v) for a number of angles on a single torus as well as the frequency

        INPUT:

           j - action (scalar)

           angle - angle (array [N])

        OUTPUT:

           ([x,vx],Omega)

        HISTORY:

           2018-04-15 - Written - Bovy (UofT)

        """
        # Find torus
        indx= numpy.argmin(numpy.fabs(j-self._js))
        if numpy.fabs(j-self._js[indx]) > 1e-10:
            raise ValueError('Given action/energy not found')
        # First we need to solve for anglea
        angle= numpy.atleast_1d(angle)
        anglea= copy.copy(angle)
        # Now iterate Newton's method
        maxiter= 100
        tol= 1.e-12
        cntr= 0
        unconv= numpy.ones(len(angle),dtype='bool')
        ta= anglea\
            +2.*numpy.sum(self._dSndJ[indx]
                  *numpy.sin(self._nforSn*numpy.atleast_2d(anglea).T),axis=1)
        dta= (ta-angle+numpy.pi) % (2.*numpy.pi)-numpy.pi
        unconv[unconv]= numpy.fabs(dta) > tol
        # Don't allow too big steps
        maxda= 2.*numpy.pi/101
        while True:
            danglea= 1.+2.*numpy.sum(\
                self._nforSn*self._dSndJ[indx]
                *numpy.cos(self._nforSn*numpy.atleast_2d(anglea[unconv]).T),
                axis=1)
            dta= (ta[unconv]-angle[unconv]+numpy.pi) % (2.*numpy.pi)-numpy.pi
            da= -dta/danglea
            da[numpy.fabs(da) > maxda]= \
                (numpy.sign(da)*maxda)[numpy.fabs(da) > maxda]
            anglea[unconv]+= da
            unconv[unconv]= numpy.fabs(dta) > tol
            newta= anglea[unconv]\
                +2.*numpy.sum(self._dSndJ[indx]
                   *numpy.sin(self._nforSn*numpy.atleast_2d(anglea[unconv]).T),
                              axis=1)
            ta[unconv]= newta
            cntr+= 1
            if numpy.sum(unconv) == 0:
                print("Took %i iterations" % cntr)
                break
            if cntr > maxiter:
                print("WARNING: DIDN'T CONVERGE IN {} iterations".format(maxiter))
                break
                raise RuntimeError("Convergence of grid-finding not achieved in %i iterations" % maxiter)
        # Then compute the auxiliary action
        ja= j+2.*numpy.sum(self._nSn[indx]
                           *numpy.cos(self._nforSn*numpy.atleast_2d(anglea).T),
                           axis=1)
        hoaainv= actionAngleHarmonicInverse(omega=self._OmegaHO[indx])
        return (*hoaainv(ja,anglea),self._Omegas[indx])
        
    def _Freqs(self,j,**kwargs):
        """
        NAME:

           Freqs

        PURPOSE:

           return the frequency corresponding to a torus

        INPUT:

           j - action (scalar)

        OUTPUT:

           (Omega)

        HISTORY:

           2018-04-08 - Written - Bovy (UofT)

        """
        # Find torus
        indx= numpy.argmin(numpy.fabs(j-self._js))
        if numpy.fabs(j-self._js[indx]) > 1e-10:
            raise ValueError('Given action/energy not found')
        return self._Omegas[indx]

def _anglea(x,E,pot,omega,vsign=1.):
    """
    NAME:
       _anglea
    PURPOSE:
       Compute the auxiliary angle in the harmonic-oscillator for a grid in x and E
    INPUT:
       x - position
       E - Energy
       pot - the potential
       omega - harmonic-oscillator frequencies
    OUTPUT:
       auxiliary angles
    HISTORY:
       2018-04-13 - Written - Bovy (UofT)
    """
    # Compute v
    v2= 2.*(E-evaluatelinearPotentials(pot,x))
    v2[v2 < 0.]= 0.
    return numpy.arctan2(omega*x,vsign*numpy.sqrt(v2))

def _danglea(x,E,pot,omega,vsign=1.):
    """
    NAME:
       _danglea
    PURPOSE:
       Compute the derivative of the auxiliary angle in the harmonic-oscillator for a grid in x and E at constant E
    INPUT:
       x - position
       E - Energy
       pot - the potential
       omega - harmonic-oscillator frequencies
    OUTPUT:
       d auxiliary angles / d x (2D array)
    HISTORY:
       2018-04-13 - Written - Bovy (UofT)
    """
    # Compute v
    v2= 2.*(E-evaluatelinearPotentials(pot,x))
    v2[v2 < 1e-10]= 2.*(E[v2<1e-10]
                        -evaluatelinearPotentials(pot,x[v2<1e-10]*(1.-1e-10)))
    anglea= numpy.arctan2(omega*x,vsign*numpy.sqrt(v2))
    return omega*numpy.cos(anglea)**2.*v2**-1.5\
        *(v2-x*evaluatelinearForces(pot,x))

def _ja(x,E,pot,omega,vsign=1.):
    """
    NAME:
       _ja
    PURPOSE:
       Compute the auxiliary action in the harmonic-oscillator for a grid in x and E
    INPUT:
       x - position
       E - Energy
       pot - the potential
       omega - harmonic-oscillator frequencies
    OUTPUT:
       auxiliary actions
    HISTORY:
       2018-04-14 - Written - Bovy (UofT)
    """
    return (E-evaluatelinearPotentials(pot,x))/omega+omega*x**2./2.

def _djadj(x,E,pot,omega,vsign=1.):
    """
    NAME:
       _djaj
    PURPOSE:
       Compute the derivative of the auxiliary action in the harmonic-oscillator wrt the action for a grid in x and E
    INPUT:
       x - position
       E - Energy
       pot - the potential
       omega - harmonic-oscillator frequencies
    OUTPUT:
       d(auxiliary actions)/d(action)
    HISTORY:
       2018-04-14 - Written - Bovy (UofT)
    """
    return 1.+(evaluatelinearForces(pot,x)+omega**2.*x)*x/(2.*(E-evaluatelinearPotentials(pot,x))-x*evaluatelinearForces(pot,x))
